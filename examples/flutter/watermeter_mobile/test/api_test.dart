import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:watermeter_mobile/api.dart';

void main() {
  final png = Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10, 0]);
  test('quota sends bearer key, refuses redirects, and removes private fields', () async {
    final api = MeterApi('fixture-key', client: MockClient((request) async {
      expect(request.url.path, '/api/open/quota');
      expect(request.headers['Authorization'], 'Bearer fixture-key');
      expect(request.followRedirects, isFalse);
      return http.Response(jsonEncode({'quota': {'account_type': 'free', 'daily_limit': 7, 'used': 2,
        'remaining': 5, 'email': 'private@example.invalid', 'api_key': 'fixture-key'}}), 200);
    }));
    expect(await api.quota(), {'account_type': 'free', 'daily_limit': 7, 'used': 2, 'remaining': 5});
    api.close();
  });
  test('multipart submission then task query uses the public routes', () async {
    final calls = <String>[];
    final api = MeterApi('fixture-key', client: MockClient((request) async {
      calls.add('${request.method} ${request.url.path}');
      if (request.method == 'POST') {
        expect(request.headers['content-type'], contains('multipart/form-data'));
        expect(latin1.decode(request.bodyBytes), contains('name="file"'));
        expect(latin1.decode(request.bodyBytes), contains('watermeter.png'));
        return http.Response('{"task_id":"mobile-1"}', 200);
      }
      return http.Response('{"status":"done","final_reading":"00123.45"}', 200);
    }));
    expect(await api.submit(png), 'mobile-1');
    expect((await api.task('mobile-1'))['final_reading'], '00123.45');
    expect(calls, ['POST /api/open/tasks', 'GET /api/open/tasks/mobile-1']);
    api.close();
  });
  test('errors never contain a key or provider body', () async {
    final api = MeterApi('fixture-key', client: MockClient((request) async => http.Response('private-provider-diagnostic', 401)));
    try { await api.quota(); fail('Expected authentication failure'); }
    on ApiFailure catch (error) {
      expect(error.status, 401); expect(error.toString(), isNot(contains('fixture-key')));
      expect(error.toString(), isNot(contains('private-provider')));
    }
    api.close();
  });
  test('429 includes server retry interval', () async {
    final api = MeterApi('fixture-key', client: MockClient((request) async => http.Response('{}', 429, headers: {'retry-after': '6'})));
    try { await api.quota(); fail('Expected rate limit'); }
    on ApiFailure catch (error) { expect(error.retryAfter, const Duration(seconds: 6)); }
    api.close();
  });
  test('broken response and missing ID are uncertain upload failures', () async {
    for (final body in ['{"task_id":', '{}', '{"task_id":"../private"}', '[]']) {
      final api = MeterApi('fixture-key', client: MockClient((request) async => http.Response(body, 200)));
      await expectLater(api.submit(png), throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 0)));
      api.close();
    }
  });
  test('bad identifiers, images, and remote HTTP do not reach transport', () async {
    var calls = 0;
    final api = MeterApi('fixture-key', client: MockClient((request) async { calls++; return http.Response('{}', 200); }));
    await expectLater(Future(() => api.task('../private')), throwsA(isA<ApiFailure>()));
    await expectLater(api.submit(Uint8List(2)), throwsA(isA<ApiFailure>()));
    expect(() => MeterApi('fixture-key', base: Uri.parse('http://example.invalid')), throwsA(isA<ApiFailure>()));
    expect(() => MeterApi('bad\r\nkey'), throwsA(isA<ApiFailure>()));
    expect(calls, 0); api.close();
  });
  test('quality rejection cannot become an accepted reading', () {
    expect(acceptedReading({'final_reading': '000.00'}), '000.00');
    expect(acceptedReading({'final_reading': '42', 'success': 'no'}), isNull);
    expect(acceptedReading({'final_reading': '42', 'result_summary': {'quality': {'status': 'review_required'}}}), isNull);
    for (final value in ['-', 'NaN', 'Infinity', '-1', '1e6', '1,000']) {
      expect(acceptedReading({'final_reading': value}), isNull);
    }
  });
}
