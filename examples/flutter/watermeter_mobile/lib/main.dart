import 'dart:math' as math;
import 'dart:typed_data';
import 'package:material_ui/material_ui.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'api.dart';
import 'controller.dart';
import 'session.dart';
import 'strings.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    final controller = MeterController(await FileSessionStore.create());
    await controller.initialize();
    runApp(WaterMeterApp(controller: controller));
  } catch (_) {
    runApp(const MaterialApp(home: Scaffold(body: SafeArea(child: Center(
      child: Text('Local storage unavailable. Please restart WaterMeter Mobile.'),
    )))));
  }
}

typedef PhotoPicker = Future<Uint8List?> Function(bool camera);
typedef LinkOpener = Future<void> Function(Uri url);

class WaterMeterApp extends StatefulWidget {
  final MeterController controller;
  final PhotoPicker? photoPicker;
  final LinkOpener? linkOpener;
  const WaterMeterApp({super.key, required this.controller, this.photoPicker, this.linkOpener});
  @override
  State<WaterMeterApp> createState() => _WaterMeterAppState();
}

class _WaterMeterAppState extends State<WaterMeterApp> with WidgetsBindingObserver {
  bool chinese = false;
  final _keyInput = TextEditingController();
  final _readingInput = TextEditingController();
  String? _lastReading;
  MeterController get c => widget.controller;
  Words get w => Words(chinese);
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    c.addListener(_updateReading);
    _updateReading();
  }
  void _updateReading() {
    if (_lastReading != c.session.aiReading) {
      _lastReading = c.session.aiReading;
      _readingInput.text = c.session.confirmedReading ?? c.session.aiReading ?? '';
    }
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive) c.pause();
  }
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    c.removeListener(_updateReading); c.pause();
    _keyInput.dispose(); _readingInput.dispose(); super.dispose();
  }

  Future<void> _action(Future<void> Function() work, {String fallback = 'storage'}) async {
    try { await work(); }
    catch (error) { c.message = error is ApiFailure ? error.kind : fallback; c.changed(); }
  }
  Future<void> _link([String suffix = '']) async {
    final url = Uri.parse('https://watermeterai.com/${chinese ? 'zh-cn' : 'en'}$suffix');
    await _action(() async {
      if (widget.linkOpener != null) { await widget.linkOpener!(url); }
      else if (!await launchUrl(url, mode: LaunchMode.externalApplication)) { throw const ApiFailure('linkError'); }
    }, fallback: 'linkError');
  }
  Future<void> _choose(bool camera) => _action(() async {
    Uint8List? bytes;
    if (widget.photoPicker != null) { bytes = await widget.photoPicker!(camera); }
    else {
      final file = await ImagePicker().pickImage(source: camera ? ImageSource.camera : ImageSource.gallery,
        imageQuality: 90, maxWidth: 2400, requestFullMetadata: false);
      if (file != null) bytes = await file.readAsBytes();
    }
    if (bytes != null) await c.selectImage(bytes);
  }, fallback: 'cameraError');

  Future<void> _recover(BuildContext pageContext) async {
    var checked = false;
    final result = await showDialog<bool>(context: pageContext, builder: (context) => StatefulBuilder(
      builder: (context, setDialogState) => AlertDialog(
        title: Text(w['resetTitle']), content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(w['resetWarning']),
          CheckboxListTile(key: const Key('history-ack'), contentPadding: EdgeInsets.zero,
            value: checked, onChanged: (value) => setDialogState(() => checked = value ?? false), title: Text(w['historyAck'])),
        ]), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(w['cancel'])),
          FilledButton(key: const Key('forget-confirm'), onPressed: checked ? () => Navigator.pop(context, true) : null,
            child: Text(w['forget'])),
        ],
      ),
    ));
    if (result == true) await _action(() => c.resetAfterHistoryCheck(historyChecked: true));
  }

  Widget _section(List<Widget> children) => Card(elevation: 0, color: Colors.white,
    child: Padding(padding: const EdgeInsets.all(20), child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch, children: children)));
  Widget _heading(String value) => Padding(padding: const EdgeInsets.only(bottom: 14),
    child: Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)));
  Widget _gap() => const SizedBox(height: 12);
  Widget _value(String label, String value) => Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(label, style: TextStyle(color: Colors.blueGrey.shade600, fontSize: 12)),
    const SizedBox(height: 6), SelectableText(value, style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w700)),
  ]));
  Widget _quota() {
    final q = c.quota;
    final fields = q['account_type'] == 'free' ? {'limit': q['daily_limit'], 'used': q['used'], 'remaining': q['remaining']} :
      {'monthly': q['monthly_remaining'], 'fixed': q['fixed_remaining']};
    return _section([_heading(w['quota']), if (q.isEmpty) Text(w['quotaUnknown']) else ...[
      if (q['account_type'] != 'free') Text(w['otherQuota']),
      _gap(), Row(children: [for (final entry in fields.entries) _value(w[entry.key], entry.value?.toString() ?? '—')]),
    ]]);
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'WaterMeter Mobile', debugShowCheckedModeBanner: false,
    locale: Locale(chinese ? 'zh' : 'en'),
    supportedLocales: const [Locale('en'), Locale('zh')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    theme: ThemeData(useMaterial3: true, colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff087f8c)),
      scaffoldBackgroundColor: const Color(0xffedf4f5),
      inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder())),
    home: AnimatedBuilder(animation: c, builder: (context, _) => Scaffold(
      appBar: AppBar(title: Text(w['title']), actions: [TextButton(key: const Key('language'),
        onPressed: () => setState(() => chinese = !chinese), child: Text(chinese ? 'English' : '中文'))]),
      body: SafeArea(child: Align(alignment: Alignment.topCenter, child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680), child: ListView(padding: const EdgeInsets.all(12), children: [
          Container(padding: const EdgeInsets.all(22), margin: const EdgeInsets.all(4),
            decoration: BoxDecoration(color: const Color(0xff073b4c), borderRadius: BorderRadius.circular(22)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(w['preview'], style: const TextStyle(color: Color(0xffa9e8dd), fontWeight: FontWeight.bold, letterSpacing: 2)),
              _gap(), Text(w['hero'], style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w800)),
              _gap(), Text(w['intro'], style: const TextStyle(color: Colors.white70)), _gap(),
              Wrap(spacing: 8, runSpacing: 8, children: [
                FilledButton.tonal(key: const Key('website'), onPressed: () => _link(), child: Text(w['website'])),
                FilledButton(key: const Key('free-key'), onPressed: () => _link('/api-keys'), child: Text(w['freeKey'])),
              ]), _gap(), Text(w['free'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
              const SizedBox(height: 5), Text(w['shared'], style: const TextStyle(color: Colors.white70, fontSize: 12)),
            ])),
          _section([_heading(w['account']),
            TextField(key: const Key('api-key'), controller: _keyInput, obscureText: true,
              autocorrect: false, enableSuggestions: false, enabled: !c.busy,
              decoration: InputDecoration(labelText: w['keyLabel'])), _gap(),
            FilledButton.tonal(key: const Key('connect'), onPressed: c.busy ? null : () async {
              await c.connect(_keyInput.text); if (c.connected) _keyInput.clear();
            }, child: Text(w['connect'])),
            _gap(), Text(w[c.connected ? 'connected' : 'keyHint'], style: const TextStyle(fontSize: 12)),
          ]),
          _section([_heading(w['capture']), Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton.icon(key: const Key('camera'), onPressed: c.canPick ? () => _choose(true) : null,
              icon: const Icon(Icons.camera_alt_outlined), label: Text(w['camera'])),
            OutlinedButton.icon(key: const Key('gallery'), onPressed: c.canPick ? () => _choose(false) : null,
              icon: const Icon(Icons.photo_library_outlined), label: Text(w['gallery'])),
            TextButton(key: const Key('demo'), onPressed: c.canPick ? () => _action(c.demo) : null, child: Text(w['demo'])),
          ]), _gap(),
            Container(height: 230, clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(color: const Color(0xffedf4f5), borderRadius: BorderRadius.circular(14)),
              child: c.session.demo ? const CustomPaint(painter: MeterIllustration()) : c.image == null ?
                Center(child: Text(w['empty'])) : InteractiveViewer(child: Image.memory(c.image!, fit: BoxFit.contain,
                  errorBuilder: (_, _, _) => Center(child: Text(w['image_type']))))),
            if (c.session.demo) ...[_gap(), Text(w['demoLabel'], style: const TextStyle(color: Colors.deepOrange, fontWeight: FontWeight.w700))],
            _gap(), Text(w['uploadNotice'], style: const TextStyle(fontSize: 12)), _gap(),
            FilledButton.icon(key: const Key('recognize'), onPressed: c.canSubmit ? c.recognize : null,
              icon: const Icon(Icons.document_scanner_outlined), label: Text(w['recognize'])),
            if (c.pending) ...[_gap(), FilledButton.tonal(key: const Key('resume'),
              onPressed: c.connected && !c.busy ? c.resume : null, child: Text(w['resume']))],
            if (c.busy) ...[_gap(), const LinearProgressIndicator(),
              if (c.session.phase != 'submitting') TextButton(onPressed: c.pause, child: Text(w['pause']))],
            _gap(), Text(w[c.session.phase], key: const Key('phase'), style: const TextStyle(fontWeight: FontWeight.w600)),
            if (c.message.isNotEmpty) ...[_gap(), Text(w[c.message], key: const Key('message'),
              style: TextStyle(color: Colors.red.shade800))],
            if (c.session.uncertain || c.pending) ...[
              TextButton(onPressed: () => _link(), child: Text(w['history'])),
              TextButton(key: const Key('recover'), onPressed: c.busy ? null : () => _recover(context), child: Text(w['reset'])),
            ],
          ]),
          if (['done', 'failed'].contains(c.session.phase)) _section([_heading(w['review']),
            Text(w['ai'], style: TextStyle(color: Colors.blueGrey.shade600)),
            SelectableText(c.session.aiReading ?? w['noReading'], key: const Key('ai-reading'),
              style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800)), _gap(),
            TextField(key: const Key('review-input'), controller: _readingInput,
              keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: w['readingInput'])), _gap(),
            OutlinedButton(key: const Key('confirm'), onPressed: c.busy ? null : () => _action(() => c.confirm(_readingInput.text)), child: Text(w['confirm'])),
            _gap(), Text('${w['confirmed']}: ${c.session.confirmedReading ?? '—'}', key: const Key('confirmed-reading')),
            _gap(), Text(w['reviewHint'], style: const TextStyle(fontSize: 12)),
          ]),
          _quota(), Padding(padding: const EdgeInsets.all(12), child: Column(children: [
            Text(w['footer'], textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)), _gap(),
            Text(w['validation'], textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: Colors.blueGrey.shade600)),
          ])),
        ]),
      ))),
    )),
  );
}

class MeterIllustration extends CustomPainter {
  const MeterIllustration();
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * .43;
    canvas.drawCircle(center, radius, Paint()..color = const Color(0xff0c6676));
    canvas.drawCircle(center, radius * .84, Paint()..color = const Color(0xfffaf9ee));
    final rect = Rect.fromCenter(center: center - const Offset(0, 10), width: radius * 1.4, height: 44);
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(5)), Paint()..color = const Color(0xff092f3a));
    final digits = TextPainter(text: const TextSpan(text: '00123.45', style: TextStyle(color: Colors.white, fontSize: 24, letterSpacing: 2)), textDirection: TextDirection.ltr)..layout();
    digits.paint(canvas, Offset(center.dx - digits.width / 2, rect.top + 8));
    final label = TextPainter(text: const TextSpan(text: 'DEMO', style: TextStyle(color: Color(0xffdc7b39), fontSize: 14, fontWeight: FontWeight.w800)), textDirection: TextDirection.ltr)..layout();
    label.paint(canvas, Offset(center.dx - label.width / 2, center.dy + 40));
  }
  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
