import json
import os
import time
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

API_BASE = os.getenv("WATERMETER_API_BASE", "https://meter.smartwebpark.com").rstrip("/")
API_KEY = os.getenv("WATERMETER_API_KEY", "")
IMAGE_PATH = Path(os.getenv("IMAGE_PATH", str(ROOT_DIR / "sample-images" / "example.jpg")))
if not IMAGE_PATH.is_absolute():
    IMAGE_PATH = ROOT_DIR / IMAGE_PATH
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
POLL_TIMEOUT_SECONDS = float(os.getenv("POLL_TIMEOUT_SECONDS", "120"))


def headers() -> dict[str, str]:
    if not API_KEY:
        raise SystemExit("Set WATERMETER_API_KEY in .env or the environment.")
    return {"Authorization": f"Bearer {API_KEY}"}


def print_json(title: str, payload: dict) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def get_json(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", headers=headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def create_task() -> str:
    if not IMAGE_PATH.is_file():
        raise SystemExit(f"Image not found: {IMAGE_PATH}")

    with IMAGE_PATH.open("rb") as image_file:
        response = requests.post(
            f"{API_BASE}/api/open/tasks",
            headers=headers(),
            files={"file": (IMAGE_PATH.name, image_file)},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    print_json("create task", payload)

    task_id = payload.get("task_id")
    if not task_id:
        raise SystemExit("No task_id returned.")
    return str(task_id)


def wait_for_task(task_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        payload = get_json(f"/api/open/tasks/{task_id}")
        print_json("task status", payload)
        if payload.get("status") in {"done", "failed"}:
            return payload
        time.sleep(POLL_INTERVAL_SECONDS)
    raise SystemExit(f"Timed out waiting for task {task_id}.")


def main() -> None:
    print_json("ai status", get_json("/api/open/ai-status"))
    print_json("quota", get_json("/api/open/quota"))
    task_id = create_task()
    final_payload = wait_for_task(task_id)
    print("\nFinal reading:", final_payload.get("final_reading", "-"))


if __name__ == "__main__":
    main()
