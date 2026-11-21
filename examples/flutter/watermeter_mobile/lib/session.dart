import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

class MeterSession {
  String phase;
  String? taskId, digest, aiReading, confirmedReading, source;
  bool uncertain, demo;
  MeterSession({this.phase = 'idle', this.taskId, this.digest, this.aiReading,
    this.confirmedReading, this.source, this.uncertain = false, this.demo = false});
  Map<String, dynamic> toJson() => {'version': 1, 'phase': phase, 'task_id': taskId,
    'digest': digest, 'ai_reading': aiReading, 'confirmed_reading': confirmedReading,
    'source': source, 'uncertain': uncertain, 'demo': demo};
  factory MeterSession.fromJson(Map<String, dynamic> data) {
    if (data['version'] != 1) throw const FormatException('Session version');
    String? field(String name) => data[name] is String ? data[name] as String : null;
    final submitting = data['phase'] == 'submitting';
    return MeterSession(phase: submitting ? 'uncertain' : (field('phase') ?? 'idle'),
      taskId: field('task_id'), digest: field('digest'), aiReading: field('ai_reading'),
      confirmedReading: field('confirmed_reading'), source: field('source'),
      uncertain: data['uncertain'] == true || submitting, demo: data['demo'] == true);
  }
}

abstract class SessionStore {
  Future<MeterSession> load();
  Future<void> save(MeterSession session);
}

class FileSessionStore implements SessionStore {
  final Directory directory;
  FileSessionStore(this.directory);
  Future<void> _tail = Future.value();
  static Future<FileSessionStore> create() async => FileSessionStore(await getApplicationSupportDirectory());
  File get _file => File('${directory.path}/watermeter_session.json');
  File get _temporary => File('${_file.path}.tmp');
  @override
  Future<MeterSession> load() async {
    // An interrupted write must not silently allow a second upload.
    if (await _temporary.exists()) return MeterSession(phase: 'uncertain', uncertain: true);
    if (!await _file.exists()) return MeterSession();
    try {
      return MeterSession.fromJson(jsonDecode(await _file.readAsString()) as Map<String, dynamic>);
    } catch (_) {
      return MeterSession(phase: 'uncertain', uncertain: true);
    }
  }
  @override
  Future<void> save(MeterSession session) {
    final encoded = jsonEncode(session.toJson());
    final work = _tail.catchError((Object _) {}).then((_) async {
      await directory.create(recursive: true);
      await _temporary.writeAsString(encoded, flush: true);
      await _temporary.rename(_file.path);
    });
    _tail = work;
    return work;
  }
}

class MemorySessionStore implements SessionStore {
  Map<String, dynamic>? value;
  @override
  Future<MeterSession> load() async => value == null ? MeterSession() : MeterSession.fromJson(value!);
  @override
  Future<void> save(MeterSession session) async { value = jsonDecode(jsonEncode(session.toJson())); }
}
