import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider/path_provider.dart';
import 'package:watermeter_mobile/api.dart';
import 'package:watermeter_mobile/controller.dart';
import 'package:watermeter_mobile/main.dart';
import 'package:watermeter_mobile/session.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('simulator demo and mock recognition workflow', (tester) async {
    final store = MemorySessionStore(); var posts = 0;
    final c = MeterController(store, pollInterval: Duration.zero, apiFactory: (key) => MeterApi(key,
      client: MockClient((request) async {
        if (request.url.path.endsWith('/quota')) return http.Response('{"quota":{"account_type":"free","daily_limit":20,"used":1,"remaining":19}}', 200);
        if (request.method == 'POST') { posts++; return http.Response('{"task_id":"simulator-fixture-1"}', 200); }
        return http.Response('{"status":"done","final_reading":"00123.45"}', 200);
      })));
    final png = base64Decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=');
    await tester.pumpWidget(WaterMeterApp(controller: c, photoPicker: (_) async => png, linkOpener: (_) async {}));
    Future<void> frames() async {
      for (var attempt = 0; attempt < 100; attempt++) {
        await tester.pump(const Duration(milliseconds: 100));
        if (!c.busy) { await tester.pump(const Duration(milliseconds: 400)); return; }
      }
      fail('The mock workflow did not finish within its bounded wait');
    }
    Future<void> screenshot(String name) async {
      await frames();
      final boundary = tester.renderObject<RenderRepaintBoundary>(find.byKey(const Key('app-surface')));
      final image = await boundary.toImage(pixelRatio: 2);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      final directory = await getTemporaryDirectory();
      await File('${directory.path}/watermeter-$name.png').writeAsBytes(data!.buffer.asUint8List(), flush: true);
      image.dispose();
    }
    Future<void> tap(String key) async {
      await tester.scrollUntilVisible(find.byKey(Key(key)), 180, scrollable: find.byType(Scrollable).first);
      await frames();
      await tester.ensureVisible(find.byKey(Key(key))); await frames();
      await tester.tap(find.byKey(Key(key))); await frames();
    }
    await tap('demo');
    await screenshot('demo-en');
    await tester.tap(find.byKey(const Key('language'))); await frames();
    await screenshot('demo-zh');
    await tester.scrollUntilVisible(find.byKey(const Key('api-key')), -180, scrollable: find.byType(Scrollable).first);
    await frames();
    await tester.enterText(find.byKey(const Key('api-key')), 'fixture-key'); await tap('connect');
    await tap('gallery'); await tap('recognize');
    expect(posts, 1); expect(c.session.aiReading, '00123.45');
    await tester.scrollUntilVisible(find.byKey(const Key('review-input')), 180, scrollable: find.byType(Scrollable).first);
    await frames();
    await tester.enterText(find.byKey(const Key('review-input')), '00123.46'); await tap('confirm');
    expect(c.session.confirmedReading, '00123.46'); expect(c.session.aiReading, '00123.45');
    expect(jsonEncode(store.value), isNot(contains('fixture-key')));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink()); c.dispose();
  });
}
