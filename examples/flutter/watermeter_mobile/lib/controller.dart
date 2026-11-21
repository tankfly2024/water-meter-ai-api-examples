import 'dart:async';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'api.dart';
import 'session.dart';

typedef ApiFactory = MeterApi Function(String key);

class MeterController extends ChangeNotifier {
  final SessionStore store;
  final ApiFactory apiFactory;
  final Duration pollInterval, pollTimeout;
  MeterSession session = MeterSession();
  Map<String, dynamic> quota = {};
  MeterApi? _api;
  Uint8List? image;
  String? imageDigest;
  String message = '';
  bool busy = false, connected = false, _paused = false, _disposed = false;
  MeterController(this.store, {ApiFactory? apiFactory, this.pollInterval = const Duration(seconds: 2),
    this.pollTimeout = const Duration(seconds: 120)}) : apiFactory = apiFactory ?? ((key) => MeterApi(key));
  bool get pending => session.taskId != null;
  bool get canPick => !busy && !pending && !session.uncertain;
  bool get canSubmit => connected && canPick && !session.demo && image != null && imageDigest != session.digest;
  void changed() { if (!_disposed) notifyListeners(); }
  Future<void> initialize() async { session = await store.load(); changed(); }
  Future<void> _save() => store.save(session);
  void _fail(Object error) { message = error is ApiFailure ? error.kind : 'storage'; }

  Future<void> connect(String key) async {
    if (busy) return;
    busy = true; connected = false; message = ''; changed();
    MeterApi? candidate;
    try {
      candidate = apiFactory(key);
      final value = await candidate.quota();
      _api?.close(); _api = candidate; candidate = null;
      connected = true; quota = value;
    } catch (error) { _fail(error); }
    finally { candidate?.close(); busy = false; changed(); }
  }

  Future<void> selectImage(Uint8List bytes) async {
    if (!canPick) throw const ApiFailure('busy');
    imageExtension(bytes);
    final digest = sha256.convert(bytes).toString();
    image = bytes; imageDigest = digest; message = '';
    if (session.digest != digest || session.demo) { session = MeterSession(); await _save(); }
    else { message = 'duplicate'; }
    changed();
  }

  Future<void> demo() async {
    if (!canPick) return;
    image = null; imageDigest = null; message = '';
    session = MeterSession(phase: 'done', demo: true, aiReading: '00123.45', source: 'demo');
    await _save(); changed();
  }

  Future<void> recognize() async {
    if (!canSubmit) return;
    busy = true; _paused = false; message = ''; changed();
    session = MeterSession(phase: 'submitting', digest: imageDigest);
    try {
      // Persist the uncertain upload marker before sending any image bytes.
      await _save(); changed();
      try {
        session.taskId = await _api!.submit(image!);
      } on ApiFailure catch (error) {
        final rejected = [400, 401, 403, 409, 413, 415, 422, 429].contains(error.status);
        session.phase = rejected ? 'failed' : 'uncertain'; session.uncertain = !rejected;
        if (rejected) session.digest = null;
        if (error.status == 401) connected = false;
        await _save(); rethrow;
      }
      session.phase = 'queued'; await _save(); changed();
      await _poll();
    } catch (error) { _fail(error); }
    finally { busy = false; changed(); }
  }

  Future<void> resume() async {
    if (busy || !connected || !pending || session.uncertain) return;
    busy = true; _paused = false; message = ''; changed();
    try { await _poll(); }
    catch (error) { _fail(error); }
    finally { busy = false; changed(); }
  }

  void pause() { _paused = true; }

  Future<void> _poll() async {
    final deadline = DateTime.now().add(pollTimeout);
    while (!_paused && !_disposed && DateTime.now().isBefore(deadline)) {
      Map<String, dynamic> result;
      try { result = await _api!.task(session.taskId!); }
      on ApiFailure catch (error) {
        if (error.status == 429) {
          final remaining = deadline.difference(DateTime.now());
          if (remaining.isNegative) break;
          await Future<void>.delayed(error.retryAfter < remaining ? error.retryAfter : remaining);
          continue;
        }
        if (error.status == 401) connected = false;
        session.phase = 'pending'; await _save(); rethrow;
      }
      final phase = result['status']?.toString();
      if (['done', 'failed', 'canceled'].contains(phase)) {
        session.phase = phase == 'done' ? 'done' : 'failed'; session.taskId = null;
        session.aiReading = phase == 'done' ? acceptedReading(result) : null;
        session.source = result['result_source'] is String ? result['result_source'] as String : null;
        await _save(); changed();
        try { quota = await _api!.quota(); }
        on ApiFailure { message = 'quota_refresh'; }
        return;
      }
      session.phase = ['queued', 'running', 'waiting_ai'].contains(phase) ? phase! : 'running';
      await _save(); changed();
      await Future<void>.delayed(pollInterval);
    }
    session.phase = 'pending'; await _save(); changed();
  }

  Future<void> confirm(String value) async {
    if (busy || !['done', 'failed'].contains(session.phase) || !validReading(value.trim())) {
      throw const ApiFailure('reading');
    }
    session.confirmedReading = value.trim(); await _save(); changed();
  }

  Future<void> resetAfterHistoryCheck({required bool historyChecked}) async {
    if (busy || !historyChecked) throw const ApiFailure('history_check');
    session = MeterSession(); message = ''; await _save(); changed();
  }

  @override
  void dispose() { _disposed = true; _paused = true; _api?.close(); super.dispose(); }
}
