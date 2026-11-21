import 'dart:convert';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:integration_test/integration_test.dart';
import 'package:watermeter_mobile/api.dart';
import 'package:watermeter_mobile/controller.dart';
import 'package:watermeter_mobile/main.dart';
import 'package:watermeter_mobile/session.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
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
    Future<void> tap(String key) async {
      await tester.scrollUntilVisible(find.byKey(Key(key)), 180, scrollable: find.byType(Scrollable).first);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(Key(key))); await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key(key))); await tester.pumpAndSettle();
    }
    await tap('demo');
    await binding.takeScreenshot('demo-en');
    await tester.tap(find.byKey(const Key('language'))); await tester.pumpAndSettle();
    await binding.takeScreenshot('demo-zh');
    await tester.scrollUntilVisible(find.byKey(const Key('api-key')), -180, scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('api-key')), 'fixture-key'); await tap('connect');
    await tap('gallery'); await tap('recognize');
    expect(posts, 1); expect(c.session.aiReading, '00123.45');
    await tester.scrollUntilVisible(find.byKey(const Key('review-input')), 180, scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('review-input')), '00123.46'); await tap('confirm');
    expect(c.session.confirmedReading, '00123.46'); expect(c.session.aiReading, '00123.45');
    expect(jsonEncode(store.value), isNot(contains('fixture-key')));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink()); c.dispose();
  });
}
