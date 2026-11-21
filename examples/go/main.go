package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

func main() {
	rootDir, _ := filepath.Abs("../..")
	loadDotenv(filepath.Join(rootDir, ".env"))
	apiBase := getenv("WATERMETER_API_BASE", "https://watermeterai.com")
	apiKey := getenv("WATERMETER_API_KEY", "")
	imagePath := getenv("IMAGE_PATH", filepath.Join(rootDir, "sample-images", "example.jpg"))
	if !filepath.IsAbs(imagePath) {
		imagePath = filepath.Join(rootDir, imagePath)
	}
	pollInterval := seconds(getenv("POLL_INTERVAL_SECONDS", "2"))
	pollTimeout := seconds(getenv("POLL_TIMEOUT_SECONDS", "120"))

	if apiKey == "" {
		panic("Set WATERMETER_API_KEY in .env or the environment.")
	}
	if _, err := os.Stat(imagePath); err != nil {
		panic("Image not found: " + imagePath)
	}

	client := &http.Client{Timeout: 60 * time.Second}
	printJSON("ai status", mustGet(client, apiBase, apiKey, "/api/open/ai-status"))
	printJSON("quota", mustGet(client, apiBase, apiKey, "/api/open/quota"))

	created := mustCreateTask(client, apiBase, apiKey, imagePath)
	printJSON("create task", created)
	taskID := stringValue(created, "task_id")
	if taskID == "" {
		panic("No task_id returned.")
	}

	deadline := time.Now().Add(pollTimeout)
	for time.Now().Before(deadline) {
		payload := mustGet(client, apiBase, apiKey, "/api/open/tasks/"+taskID)
		printJSON("task status", payload)
		status := stringValue(payload, "status")
		if status == "done" || status == "failed" {
			fmt.Println("\nFinal reading:", dash(stringValue(payload, "final_reading")))
			return
		}
		time.Sleep(pollInterval)
	}
	panic("Timed out waiting for task " + taskID + ".")
}

func mustGet(client *http.Client, apiBase, apiKey, path string) map[string]any {
	request, _ := http.NewRequest(http.MethodGet, trimSlash(apiBase)+path, nil)
	request.Header.Set("Authorization", "Bearer "+apiKey)
	return mustSend(client, request)
}

func mustCreateTask(client *http.Client, apiBase, apiKey, imagePath string) map[string]any {
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	file, err := os.Open(imagePath)
	if err != nil {
		panic(err)
	}
	defer file.Close()

	part, err := writer.CreateFormFile("file", filepath.Base(imagePath))
	if err != nil {
		panic(err)
	}
	if _, err := io.Copy(part, file); err != nil {
		panic(err)
	}
	writer.Close()

	request, _ := http.NewRequest(http.MethodPost, trimSlash(apiBase)+"/api/open/tasks", &body)
	request.Header.Set("Authorization", "Bearer "+apiKey)
	request.Header.Set("Content-Type", writer.FormDataContentType())
	return mustSend(client, request)
}

func mustSend(client *http.Client, request *http.Request) map[string]any {
	response, err := client.Do(request)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(response.Body)
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		panic(fmt.Sprintf("%d: %s", response.StatusCode, string(body)))
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		panic(err)
	}
	return payload
}

func printJSON(title string, payload map[string]any) {
	pretty, _ := json.MarshalIndent(payload, "", "  ")
	fmt.Printf("\n== %s ==\n%s\n", title, string(pretty))
}

func stringValue(payload map[string]any, name string) string {
	if value, ok := payload[name].(string); ok {
		return value
	}
	return ""
}

func getenv(name, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}

func loadDotenv(path string) {
	content, err := os.ReadFile(path)
	if err != nil {
		return
	}
	for _, rawLine := range bytes.Split(content, []byte("\n")) {
		line := string(bytes.TrimSpace(rawLine))
		if line == "" || line[0] == '#' {
			continue
		}
		parts := bytes.SplitN([]byte(line), []byte("="), 2)
		if len(parts) != 2 {
			continue
		}
		key := string(bytes.TrimSpace(parts[0]))
		value := string(bytes.Trim(bytes.TrimSpace(parts[1]), `"'`))
		if os.Getenv(key) == "" {
			os.Setenv(key, value)
		}
	}
}

func seconds(value string) time.Duration {
	duration, err := time.ParseDuration(value + "s")
	if err != nil {
		panic(err)
	}
	return duration
}

func trimSlash(value string) string {
	for len(value) > 0 && value[len(value)-1] == '/' {
		value = value[:len(value)-1]
	}
	return value
}

func dash(value string) string {
	if value == "" {
		return "-"
	}
	return value
}
