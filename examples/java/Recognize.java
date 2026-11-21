import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Recognize {
    private static final Path ROOT_DIR = Path.of("../..").toAbsolutePath().normalize();
    private static final Map<String, String> DOTENV = loadDotenv(ROOT_DIR.resolve(".env"));
    private static final String API_BASE = getenv("WATERMETER_API_BASE", "https://watermeterai.com").replaceAll("/$", "");
    private static final String API_KEY = getenv("WATERMETER_API_KEY", "");
    private static final Path IMAGE_PATH = resolveImagePath(getenv("IMAGE_PATH", ROOT_DIR.resolve("sample-images/example.jpg").toString()));
    private static final long POLL_INTERVAL_MS = Long.parseLong(getenv("POLL_INTERVAL_SECONDS", "2")) * 1000L;
    private static final long POLL_TIMEOUT_MS = Long.parseLong(getenv("POLL_TIMEOUT_SECONDS", "120")) * 1000L;
    private static final HttpClient CLIENT = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(30)).build();

    public static void main(String[] args) throws Exception {
        if (API_KEY.isBlank()) {
            throw new IllegalStateException("Set WATERMETER_API_KEY in .env or the environment.");
        }
        if (!Files.isRegularFile(IMAGE_PATH)) {
            throw new IllegalStateException("Image not found: " + IMAGE_PATH);
        }

        printJson("ai status", getJson("/api/open/ai-status"));
        printJson("quota", getJson("/api/open/quota"));
        String created = createTask();
        printJson("create task", created);

        String taskId = extractString(created, "task_id");
        if (taskId.isBlank()) {
            throw new IllegalStateException("No task_id returned.");
        }

        String finalPayload = waitForTask(taskId);
        System.out.println("\nFinal reading: " + valueOrDash(extractString(finalPayload, "final_reading")));
    }

    private static String getJson(String path) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create(API_BASE + path))
                .header("Authorization", "Bearer " + API_KEY)
                .GET()
                .build();
        return send(request);
    }

    private static String createTask() throws IOException, InterruptedException {
        String boundary = "----WaterMeterBoundary" + UUID.randomUUID();
        byte[] body = multipartBody(boundary, IMAGE_PATH);
        HttpRequest request = HttpRequest.newBuilder(URI.create(API_BASE + "/api/open/tasks"))
                .header("Authorization", "Bearer " + API_KEY)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(body))
                .build();
        return send(request);
    }

    private static String waitForTask(String taskId) throws IOException, InterruptedException {
        long deadline = System.currentTimeMillis() + POLL_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            String payload = getJson("/api/open/tasks/" + taskId);
            printJson("task status", payload);
            String status = extractString(payload, "status");
            if ("done".equals(status) || "failed".equals(status)) {
                return payload;
            }
            Thread.sleep(POLL_INTERVAL_MS);
        }
        throw new IllegalStateException("Timed out waiting for task " + taskId + ".");
    }

    private static String send(HttpRequest request) throws IOException, InterruptedException {
        HttpResponse<String> response = CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException(response.statusCode() + ": " + response.body());
        }
        return response.body();
    }

    private static byte[] multipartBody(String boundary, Path imagePath) throws IOException {
        String filename = imagePath.getFileName().toString();
        String prefix = "--" + boundary + "\r\n"
                + "Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + "\"\r\n"
                + "Content-Type: application/octet-stream\r\n\r\n";
        String suffix = "\r\n--" + boundary + "--\r\n";
        byte[] fileBytes = Files.readAllBytes(imagePath);
        byte[] prefixBytes = prefix.getBytes(StandardCharsets.UTF_8);
        byte[] suffixBytes = suffix.getBytes(StandardCharsets.UTF_8);
        byte[] body = new byte[prefixBytes.length + fileBytes.length + suffixBytes.length];
        System.arraycopy(prefixBytes, 0, body, 0, prefixBytes.length);
        System.arraycopy(fileBytes, 0, body, prefixBytes.length, fileBytes.length);
        System.arraycopy(suffixBytes, 0, body, prefixBytes.length + fileBytes.length, suffixBytes.length);
        return body;
    }

    private static String extractString(String json, String field) {
        Pattern pattern = Pattern.compile("\"" + Pattern.quote(field) + "\"\\s*:\\s*\"([^\"]*)\"");
        Matcher matcher = pattern.matcher(json);
        return matcher.find() ? matcher.group(1) : "";
    }

    private static String getenv(String name, String fallback) {
        String value = System.getenv(name);
        if ((value == null || value.isBlank()) && DOTENV.containsKey(name)) {
            value = DOTENV.get(name);
        }
        return value == null || value.isBlank() ? fallback : value;
    }

    private static Path resolveImagePath(String rawPath) {
        Path path = Path.of(rawPath);
        return path.isAbsolute() ? path : ROOT_DIR.resolve(path).normalize();
    }

    private static Map<String, String> loadDotenv(Path path) {
        Map<String, String> values = new HashMap<>();
        if (!Files.isRegularFile(path)) {
            return values;
        }
        try {
            for (String rawLine : Files.readAllLines(path, StandardCharsets.UTF_8)) {
                String line = rawLine.trim();
                if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) {
                    continue;
                }
                String[] parts = line.split("=", 2);
                values.put(parts[0].trim(), parts[1].trim().replaceAll("^['\"]|['\"]$", ""));
            }
        } catch (IOException ignored) {
            return values;
        }
        return values;
    }

    private static String valueOrDash(String value) {
        return value == null || value.isBlank() ? "-" : value;
    }

    private static void printJson(String title, String payload) {
        System.out.println("\n== " + title + " ==");
        System.out.println(payload);
    }
}
