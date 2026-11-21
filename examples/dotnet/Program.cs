using System.Net.Http.Headers;
using System.Text.Json;

var rootDir = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".."));
LoadDotEnv(Path.Combine(rootDir, ".env"));
var apiBase = (Environment.GetEnvironmentVariable("WATERMETER_API_BASE") ?? "https://watermeterai.com").TrimEnd('/');
var apiKey = Environment.GetEnvironmentVariable("WATERMETER_API_KEY") ?? "";
var imagePath = Environment.GetEnvironmentVariable("IMAGE_PATH") ?? Path.Combine(rootDir, "sample-images", "example.jpg");
if (!Path.IsPathRooted(imagePath))
{
    imagePath = Path.Combine(rootDir, imagePath);
}
var pollInterval = TimeSpan.FromSeconds(double.Parse(Environment.GetEnvironmentVariable("POLL_INTERVAL_SECONDS") ?? "2"));
var pollTimeout = TimeSpan.FromSeconds(double.Parse(Environment.GetEnvironmentVariable("POLL_TIMEOUT_SECONDS") ?? "120"));

if (string.IsNullOrWhiteSpace(apiKey))
{
    throw new InvalidOperationException("Set WATERMETER_API_KEY in .env or the environment.");
}

if (!File.Exists(imagePath))
{
    throw new FileNotFoundException("Image not found.", imagePath);
}

using var client = new HttpClient { BaseAddress = new Uri(apiBase) };
client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);

PrintJson("ai status", await GetJsonAsync("/api/open/ai-status"));
PrintJson("quota", await GetJsonAsync("/api/open/quota"));

var created = await CreateTaskAsync();
PrintJson("create task", created);
var taskId = GetString(created, "task_id");
if (string.IsNullOrWhiteSpace(taskId))
{
    throw new InvalidOperationException("No task_id returned.");
}

var finalPayload = await WaitForTaskAsync(taskId);
Console.WriteLine($"\nFinal reading: {GetString(finalPayload, "final_reading") ?? "-"}");

async Task<JsonDocument> GetJsonAsync(string path)
{
    using var response = await client.GetAsync(path);
    var content = await response.Content.ReadAsStringAsync();
    response.EnsureSuccessStatusCode();
    return JsonDocument.Parse(content);
}

async Task<JsonDocument> CreateTaskAsync()
{
    using var form = new MultipartFormDataContent();
    await using var stream = File.OpenRead(imagePath);
    using var fileContent = new StreamContent(stream);
    fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
    form.Add(fileContent, "file", Path.GetFileName(imagePath));

    using var response = await client.PostAsync("/api/open/tasks", form);
    var content = await response.Content.ReadAsStringAsync();
    response.EnsureSuccessStatusCode();
    return JsonDocument.Parse(content);
}

async Task<JsonDocument> WaitForTaskAsync(string currentTaskId)
{
    using var timeout = new CancellationTokenSource(pollTimeout);
    while (!timeout.IsCancellationRequested)
    {
        var payload = await GetJsonAsync($"/api/open/tasks/{Uri.EscapeDataString(currentTaskId)}");
        PrintJson("task status", payload);
        var status = GetString(payload, "status");
        if (status is "done" or "failed")
        {
            return payload;
        }
        await Task.Delay(pollInterval, timeout.Token);
    }

    throw new TimeoutException($"Timed out waiting for task {currentTaskId}.");
}

static string? GetString(JsonDocument document, string name)
{
    return document.RootElement.TryGetProperty(name, out var value) ? value.GetString() : null;
}

static void PrintJson(string title, JsonDocument payload)
{
    Console.WriteLine($"\n== {title} ==");
    Console.WriteLine(JsonSerializer.Serialize(payload.RootElement, new JsonSerializerOptions { WriteIndented = true }));
}

static void LoadDotEnv(string path)
{
    if (!File.Exists(path))
    {
        return;
    }

    foreach (var rawLine in File.ReadLines(path))
    {
        var line = rawLine.Trim();
        if (line.Length == 0 || line.StartsWith('#') || !line.Contains('='))
        {
            continue;
        }

        var parts = line.Split('=', 2);
        var key = parts[0].Trim();
        var value = parts[1].Trim().Trim('"', '\'');
        Environment.SetEnvironmentVariable(key, Environment.GetEnvironmentVariable(key) ?? value);
    }
}
