import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:watermeter_mobile/api.dart';
import 'package:watermeter_mobile/controller.dart';
import 'package:watermeter_mobile/session.dart';
import 'package:watermeter_mobile/strings.dart';

class FakeService {
  int posts = 0, gets = 0, limit = 20, submitStatus = 200;
  bool brokenSubmit = false, failedQuality = false, quotaFailure = false;
  final MemorySessionStore store;
  FakeService(this.store);
  Future<http.Response> call(http.Request request) async {
    if (request.url.path.endsWith('/quota')) {
      if (quotaFailure) return http.Response('{}', 503);
      return http.Response(jsonEncode({'quota': {'account_type': 'free', 'daily_limit': limit, 'used': posts, 'remaining': limit - posts}}), 200);
    }
    if (request.method == 'POST') {
      expect(store.value?['phase'], 'submitting'); posts++;
      if (brokenSubmit) throw TimeoutException('fixture');
      return http.Response('{"task_id":"mobile-1"}', submitStatus);
    }
    gets++;
    return http.Response(jsonEncode({'status': 'done', 'final_reading': '00123.45',
      'result_summary': {'quality': {'status': failedQuality ? 'unreadable' : 'accepted'}}}), 200);
  }
  MeterApi api(String key) => MeterApi(key, client: MockClient(call));
}

void main() {
  final image = Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10, 1]);
  MeterController create(MemorySessionStore store, FakeService service, {Duration timeout = const Duration(seconds: 2)}) =>
      MeterController(store, apiFactory: service.api, pollInterval: Duration.zero, pollTimeout: timeout);

  test('image is local until start; AI and confirmation remain separate', () async {
    final store = MemorySessionStore(); final service = FakeService(store); final c = create(store, service);
    await c.initialize(); await c.connect('fixture-key'); await c.selectImage(image);
    expect(service.posts, 0); await c.recognize();
    expect(service.posts, 1); expect(c.session.aiReading, '00123.45'); expect(c.session.confirmedReading, isNull);
    await c.confirm('00123.46'); expect(c.session.aiReading, '00123.45'); expect(c.session.confirmedReading, '00123.46');
    expect(c.quota['remaining'], 19); expect(jsonEncode(store.value), isNot(contains('fixture-key'))); c.dispose();
  });
  test('same image bytes never cause a second submission', () async {
    final store = MemorySessionStore(); final service = FakeService(store); final c = create(store, service);
    await c.connect('fixture-key'); await c.selectImage(image); await c.recognize();
    await c.selectImage(image); await c.recognize(); expect(service.posts, 1); expect(c.message, 'duplicate'); c.dispose();
  });
  test('unknown upload survives restart and blocks new uploads', () async {
    final store = MemorySessionStore(); final service = FakeService(store)..brokenSubmit = true;
    final c = create(store, service); await c.connect('fixture-key'); await c.selectImage(image); await c.recognize();
    expect(c.session.uncertain, isTrue); c.dispose();
    final restored = create(store, service); await restored.initialize(); await restored.connect('fixture-key');
    expect(restored.canPick, isFalse); await restored.recognize(); expect(service.posts, 1);
    await expectLater(restored.resetAfterHistoryCheck(historyChecked: false), throwsA(isA<ApiFailure>()));
    await restored.resetAfterHistoryCheck(historyChecked: true); expect(restored.canPick, isTrue); expect(service.posts, 1); restored.dispose();
  });
  test('explicit upload rejection requires a manual retry', () async {
    final store = MemorySessionStore(); final service = FakeService(store)..submitStatus = 429;
    final c = create(store, service); await c.connect('fixture-key'); await c.selectImage(image); await c.recognize();
    expect(service.posts, 1); expect(c.session.uncertain, isFalse); expect(c.canSubmit, isTrue);
    service.submitStatus = 200; await c.recognize(); expect(service.posts, 2); c.dispose();
  });
  test('timeout and restart resume GET only with the saved task ID', () async {
    final store = MemorySessionStore(); final service = FakeService(store); final c = create(store, service, timeout: Duration.zero);
    await c.connect('fixture-key'); await c.selectImage(image); await c.recognize();
    expect(c.session.phase, 'pending'); expect(service.posts, 1); c.dispose();
    final restored = create(store, service); await restored.initialize(); expect(restored.connected, isFalse);
    await restored.connect('fixture-key'); await restored.resume(); expect(service.posts, 1); expect(service.gets, 1); restored.dispose();
  });
  test('a crash marker becomes uncertain, and local data contains no key', () async {
    final store = MemorySessionStore(); await store.save(MeterSession(phase: 'submitting', digest: 'fixture-digest'));
    final c = create(store, FakeService(store)); await c.initialize(); expect(c.session.uncertain, isTrue);
    expect(c.canPick, isFalse); expect(store.value!.keys, isNot(contains('api_key'))); c.dispose();
  });
  test('offline demo does not call the API and is explicitly marked', () async {
    final store = MemorySessionStore(); final service = FakeService(store); final c = create(store, service);
    await c.demo(); expect(c.session.demo, isTrue); expect(c.canSubmit, isFalse); expect(service.posts, 0);
    await c.confirm('00123.46'); expect(c.session.aiReading, '00123.45'); c.dispose();
  });
  test('quality rejected reading stays empty while manual value is separate', () async {
    final store = MemorySessionStore(); final service = FakeService(store)..failedQuality = true;
    final c = create(store, service); await c.connect('fixture-key'); await c.selectImage(image); await c.recognize();
    expect(c.session.aiReading, isNull); await c.confirm('123.40'); expect(c.session.aiReading, isNull);
    expect(c.session.confirmedReading, '123.40'); await expectLater(c.confirm('=1+1'), throwsA(isA<ApiFailure>())); c.dispose();
  });
  test('custom quota is not replaced by twenty', () async {
    for (final limit in [0, 7, 20]) {
      final store = MemorySessionStore(); final service = FakeService(store)..limit = limit;
      final c = create(store, service); await c.connect('fixture-key'); expect(c.quota['daily_limit'], limit); c.dispose();
    }
  });
  test('atomic file store restores task ID and fails closed on corruption', () async {
    final directory = await Directory.systemTemp.createTemp('watermeter-store-test-');
    final store = FileSessionStore(directory);
    try {
      await store.save(MeterSession(phase: 'pending', taskId: 'task-1'));
      expect((await store.load()).taskId, 'task-1');
      await File('${directory.path}/watermeter_session.json.tmp').writeAsString('{');
      expect((await store.load()).uncertain, isTrue);
    } finally { await directory.delete(recursive: true); }
  });
  test('translations contain the same business keys', () {
    expect(Words.zh.keys.toSet(), Words.en.keys.toSet());
  });
}
