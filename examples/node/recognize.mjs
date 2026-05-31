import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import FormData from "form-data";
import fetch from "node-fetch";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "../..");
dotenv.config({ path: path.join(rootDir, ".env") });

const apiBase = (process.env.WATERMETER_API_BASE || "https://meter.smartwebpark.com").replace(/\/$/, "");
const apiKey = process.env.WATERMETER_API_KEY || "";
const rawImagePath = process.env.IMAGE_PATH || path.join(rootDir, "sample-images", "example.jpg");
const imagePath = path.isAbsolute(rawImagePath) ? rawImagePath : path.join(rootDir, rawImagePath);
const pollIntervalMs = Number(process.env.POLL_INTERVAL_SECONDS || "2") * 1000;
const pollTimeoutMs = Number(process.env.POLL_TIMEOUT_SECONDS || "120") * 1000;

if (!apiKey) {
  throw new Error("Set WATERMETER_API_KEY in .env or the environment.");
}

function authHeaders() {
  return { Authorization: `Bearer ${apiKey}` };
}

async function readJson(response) {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}: ${JSON.stringify(payload)}`);
  }
  return payload;
}

function printJson(title, payload) {
  console.log(`\n== ${title} ==`);
  console.log(JSON.stringify(payload, null, 2));
}

async function getJson(pathname) {
  const response = await fetch(`${apiBase}${pathname}`, { headers: authHeaders() });
  return readJson(response);
}

async function createTask() {
  if (!fs.existsSync(imagePath)) {
    throw new Error(`Image not found: ${imagePath}`);
  }

  const form = new FormData();
  form.append("file", fs.createReadStream(imagePath), path.basename(imagePath));

  const response = await fetch(`${apiBase}/api/open/tasks`, {
    method: "POST",
    headers: { ...authHeaders(), ...form.getHeaders() },
    body: form,
  });
  const payload = await readJson(response);
  printJson("create task", payload);

  if (!payload.task_id) {
    throw new Error("No task_id returned.");
  }
  return payload.task_id;
}

async function waitForTask(taskId) {
  const deadline = Date.now() + pollTimeoutMs;
  while (Date.now() < deadline) {
    const payload = await getJson(`/api/open/tasks/${encodeURIComponent(taskId)}`);
    printJson("task status", payload);
    if (payload.status === "done" || payload.status === "failed") {
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }
  throw new Error(`Timed out waiting for task ${taskId}.`);
}

printJson("ai status", await getJson("/api/open/ai-status"));
printJson("quota", await getJson("/api/open/quota"));
const taskId = await createTask();
const finalPayload = await waitForTask(taskId);
console.log("\nFinal reading:", finalPayload.final_reading || "-");
