<?php

$rootDir = realpath(__DIR__ . "/../..");
loadDotenv($rootDir . "/.env");
$apiBase = rtrim(getenv("WATERMETER_API_BASE") ?: "https://watermeterai.com", "/");
$apiKey = getenv("WATERMETER_API_KEY") ?: "";
$imagePath = getenv("IMAGE_PATH") ?: $rootDir . "/sample-images/example.jpg";
if (!preg_match('/^([A-Za-z]:[\/\\\\]|\/)/', $imagePath)) {
    $imagePath = $rootDir . "/" . ltrim($imagePath, "./\\");
}
$pollIntervalSeconds = (int)(getenv("POLL_INTERVAL_SECONDS") ?: "2");
$pollTimeoutSeconds = (int)(getenv("POLL_TIMEOUT_SECONDS") ?: "120");

if ($apiKey === "") {
    fwrite(STDERR, "Set WATERMETER_API_KEY in .env or the environment.\n");
    exit(1);
}

if (!is_file($imagePath)) {
    fwrite(STDERR, "Image not found: {$imagePath}\n");
    exit(1);
}

printJson("ai status", getJson("/api/open/ai-status"));
printJson("quota", getJson("/api/open/quota"));

$created = postFile("/api/open/tasks", $imagePath);
printJson("create task", $created);
$taskId = $created["task_id"] ?? "";
if ($taskId === "") {
    fwrite(STDERR, "No task_id returned.\n");
    exit(1);
}

$deadline = time() + $pollTimeoutSeconds;
while (time() < $deadline) {
    $payload = getJson("/api/open/tasks/" . rawurlencode($taskId));
    printJson("task status", $payload);
    $status = $payload["status"] ?? "";
    if ($status === "done" || $status === "failed") {
        echo "\nFinal reading: " . ($payload["final_reading"] ?? "-") . "\n";
        exit(0);
    }
    sleep($pollIntervalSeconds);
}

fwrite(STDERR, "Timed out waiting for task {$taskId}.\n");
exit(1);

function getJson(string $path): array
{
    global $apiBase, $apiKey;
    $ch = curl_init($apiBase . $path);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => ["Authorization: Bearer {$apiKey}"],
    ]);
    return send($ch);
}

function postFile(string $path, string $imagePath): array
{
    global $apiBase, $apiKey;
    $ch = curl_init($apiBase . $path);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_HTTPHEADER => ["Authorization: Bearer {$apiKey}"],
        CURLOPT_POSTFIELDS => ["file" => new CURLFile($imagePath)],
    ]);
    return send($ch);
}

function send($ch): array
{
    $body = curl_exec($ch);
    if ($body === false) {
        throw new RuntimeException(curl_error($ch));
    }
    $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($statusCode < 200 || $statusCode >= 300) {
        throw new RuntimeException("{$statusCode}: {$body}");
    }
    return json_decode($body, true, flags: JSON_THROW_ON_ERROR);
}

function printJson(string $title, array $payload): void
{
    echo "\n== {$title} ==\n";
    echo json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
}

function loadDotenv(string $path): void
{
    if (!is_file($path)) {
        return;
    }
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === "" || str_starts_with($line, "#") || !str_contains($line, "=")) {
            continue;
        }
        [$key, $value] = explode("=", $line, 2);
        $key = trim($key);
        $value = trim(trim($value), "\"'");
        if (getenv($key) === false) {
            putenv("{$key}={$value}");
        }
    }
}
