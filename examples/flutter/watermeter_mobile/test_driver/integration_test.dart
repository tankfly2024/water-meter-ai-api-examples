import 'dart:io';
import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() async {
  final output = Directory(Platform.environment['WM_SCREENSHOT_DIR'] ?? 'screenshots');
  await output.create(recursive: true);
  await integrationDriver(onScreenshot: (name, bytes, [args]) async {
    if (!RegExp(r'^demo-(en|zh)$').hasMatch(name)) return false;
    await File('${output.path}/$name.png').writeAsBytes(bytes, flush: true);
    return true;
  });
}
