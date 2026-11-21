import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:watermeter_mobile/controller.dart';
import 'package:watermeter_mobile/main.dart';
import 'package:watermeter_mobile/session.dart';

void main() {
  testWidgets('390px preview promotes free API, supports Chinese and offline review', (tester) async {
    tester.view.physicalSize = const Size(390, 844); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final c = MeterController(MemorySessionStore()); final links = <Uri>[];
    await tester.pumpWidget(WaterMeterApp(controller: c, linkOpener: (url) async { links.add(url); }));
    expect(find.text('Free account: 20 recognitions per day'), findsOneWidget);
    await tester.tap(find.byKey(const Key('free-key'))); await tester.pumpAndSettle();
    expect(links.single.toString(), 'https://watermeterai.com/en/api-keys');
    await tester.scrollUntilVisible(find.byKey(const Key('demo')), 200); await tester.tap(find.byKey(const Key('demo')));
    await tester.pumpAndSettle(); expect(c.session.demo, isTrue);
    await tester.scrollUntilVisible(find.byKey(const Key('review-input')), 200);
    await tester.enterText(find.byKey(const Key('review-input')), '00123.46');
    await tester.ensureVisible(find.byKey(const Key('confirm'))); await tester.tap(find.byKey(const Key('confirm'))); await tester.pumpAndSettle();
    expect(c.session.confirmedReading, '00123.46');
    await tester.tap(find.byKey(const Key('language'))); await tester.pumpAndSettle();
    expect(find.text('WaterMeter 水表识别'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink()); c.dispose();
  });
}
