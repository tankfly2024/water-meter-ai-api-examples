import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

class ApiFailure implements Exception {
  final int status;
  final String kind;
  final Duration retryAfter;
  const ApiFailure(this.kind, {this.status = 0, this.retryAfter = const Duration(seconds: 2)});
  @override
  String toString() => 'WaterMeter API: $kind${status == 0 ? '' : ' ($status)'}';
}

String imageExtension(Uint8List bytes) {
  if (bytes.isEmpty || bytes.length > 20 * 1024 * 1024) {
    throw const ApiFailure('image_size');
  }
  bool starts(List<int> signature) => bytes.length >= signature.length &&
      List.generate(signature.length, (i) => bytes[i] == signature[i]).every((v) => v);
  if (starts([255, 216, 255])) return 'jpg';
  if (starts([137, 80, 78, 71, 13, 10, 26, 10])) return 'png';
  if (bytes.length >= 12 && ascii.decode(bytes.sublist(0, 4), allowInvalid: true) == 'RIFF' &&
      ascii.decode(bytes.sublist(8, 12), allowInvalid: true) == 'WEBP') return 'webp';
  throw const ApiFailure('image_type');
}

String? acceptedReading(Map<String, dynamic> result) {
  final summary = result['result_summary'] is Map ? result['result_summary'] as Map : {};
  final quality = summary['quality'] is Map ? summary['quality'] as Map :
      (result['quality'] is Map ? result['quality'] as Map : {});
  if (result['success'] == 'no' || summary['success'] == 'no' ||
      ['review_required', 'unreadable'].contains(quality['status'])) return null;
  final value = result['final_reading']?.toString() ?? '';
  return validReading(value) ? value : null;
}

bool validReading(String value) => RegExp(r'^\d+(\.\d+)?$').hasMatch(value) &&
    (double.tryParse(value)?.isFinite ?? false);

class MeterApi {
  final String _key;
  final http.Client _client;
  final Uri base;
  final Duration timeout;
  MeterApi(String key, {http.Client? client, Uri? base, this.timeout = const Duration(seconds: 30)})
      : _key = key.trim(), _client = client ?? http.Client(), base = base ?? Uri.parse('https://watermeterai.com') {
    if (_key.isEmpty || _key.contains(RegExp(r'[\r\n]'))) throw const ApiFailure('key');
    final local = this.base.scheme == 'http' && ['localhost', '127.0.0.1', '::1'].contains(this.base.host);
    if ((!local && this.base.scheme != 'https') || this.base.host.isEmpty ||
        this.base.userInfo.isNotEmpty || this.base.hasQuery || this.base.hasFragment ||
        !['', '/'].contains(this.base.path)) throw const ApiFailure('endpoint');
  }

  Future<Map<String, dynamic>> _send(http.BaseRequest request) async {
    request.followRedirects = false;
    request.headers['Authorization'] = 'Bearer $_key';
    request.headers['Accept'] = 'application/json';
    try {
      final response = await _client.send(request).timeout(timeout);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        await response.stream.drain<void>().timeout(timeout);
        throw ApiFailure(response.statusCode == 401 ? 'auth' : 'http', status: response.statusCode,
            retryAfter: Duration(seconds: (int.tryParse(response.headers['retry-after'] ?? '') ?? 2).clamp(1, 120).toInt()));
      }
      final chunks = <int>[];
      await for (final chunk in response.stream.timeout(timeout)) {
        chunks.addAll(chunk);
        if (chunks.length > 4 * 1024 * 1024) throw const ApiFailure('response');
      }
      final value = jsonDecode(utf8.decode(chunks));
      if (value is! Map<String, dynamic>) throw const ApiFailure('response');
      return value;
    } on ApiFailure {
      rethrow;
    } catch (_) {
      // Never expose headers, credentials, provider bodies, or local image paths.
      throw const ApiFailure('network');
    }
  }

  Future<Map<String, dynamic>> quota() async {
    final payload = await _send(http.Request('GET', base.resolve('/api/open/quota')));
    final value = payload['quota'];
    if (value is! Map) throw const ApiFailure('response');
    const fields = ['account_type', 'daily_limit', 'used', 'remaining', 'monthly_remaining',
      'monthly_bonus_remaining', 'fixed_remaining', 'is_unlimited'];
    return {for (final key in fields) if (value[key] is String || value[key] is num || value[key] is bool) key: value[key]};
  }

  Future<String> submit(Uint8List bytes) async {
    final extension = imageExtension(bytes);
    final request = http.MultipartRequest('POST', base.resolve('/api/open/tasks'));
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'watermeter.$extension'));
    final result = await _send(request);
    final id = result['task_id']?.toString() ?? '';
    if (!RegExp(r'^[A-Za-z0-9_-]{1,160}$').hasMatch(id)) throw const ApiFailure('response');
    return id;
  }

  Future<Map<String, dynamic>> task(String id) {
    if (!RegExp(r'^[A-Za-z0-9_-]{1,160}$').hasMatch(id)) throw const ApiFailure('task_id');
    return _send(http.Request('GET', base.resolve('/api/open/tasks/$id')));
  }

  void close() => _client.close();
}
