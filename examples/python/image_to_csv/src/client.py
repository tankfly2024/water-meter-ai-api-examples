"""Local-only review UI and a public WaterMeter API client; standard library only."""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import secrets
import threading
import uuid
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ASSETS = Path(__file__).resolve().parent
MAX_IMAGE = 20 * 1024 * 1024
TERMINAL = {"accepted", "unreadable", "failed", "submission_unknown"}


class ApiError(Exception):
    def __init__(self, message, status=0, retry_after=2):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicApi:
    def __init__(self, base, key):
        target = urlsplit(base)
        loopback = target.hostname in {"127.0.0.1", "localhost", "::1"}
        if (target.scheme != "https" and not (target.scheme == "http" and loopback)) or not target.hostname:
            raise ValueError("Use an HTTPS API address, or HTTP loopback for local tests.")
        if target.username or target.password or target.query or target.fragment or target.path not in {"", "/"}:
            raise ValueError("The API base must contain only a scheme, host, and optional port.")
        if not key or any(c in key for c in "\r\n"):
            raise ValueError("An API key is required.")
        self.base, self.key = base.rstrip("/"), key
        self.opener = build_opener(NoRedirect())

    def request(self, path, data=None, content_type=None):
        headers = {"Authorization": "Bearer " + self.key, "User-Agent": "WaterMeter-ImageToCSV/0.1"}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                payload = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError()
            return payload
        except HTTPError as exc:
            retry = exc.headers.get("Retry-After", "2")
            raise ApiError("API returned HTTP " + str(exc.code), exc.code,
                           min(120, max(1, int(retry))) if retry.isdigit() else 2) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise ApiError("The API response could not be confirmed. No automatic submission retry.") from None
        except (ValueError, UnicodeError):
            raise ApiError("The API returned an invalid response.") from None

    def submit(self, row, data):
        boundary = "wmeter" + secrets.token_hex(16)
        # The upload identifier is generated locally, never derived from an untrusted filename.
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{row['id']}{row['extension']}\"\r\n"
                f"Content-Type: {row['mime']}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        result = self.request("/api/open/tasks", body, "multipart/form-data; boundary=" + boundary)
        task_id = result.get("task_id")
        if not isinstance(task_id, (str, int)) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", str(task_id)):
            raise ApiError("Submission response has no usable task ID. Check account history before resubmitting.")
        return str(task_id)


def image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise ValueError("Choose a JPEG, PNG, or WEBP image.")


def final_reading(payload):
    summary = payload.get("result_summary") or {}
    summary = summary if isinstance(summary, dict) else {}
    quality = summary.get("quality") or payload.get("quality") or {}
    quality = quality if isinstance(quality, dict) else {}
    if payload.get("success") == "no" or summary.get("success") == "no" or quality.get("status") in {"review_required", "unreadable"}:
        return ""
    value = payload.get("final_reading")
    value = "" if value is None else str(value)
    return value if re.fullmatch(r"\d+(?:\.\d+)?", value) else ""


def spreadsheet_text(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value


class ReviewStore:
    def __init__(self, directory, api_base="https://watermeterai.com", key="", poll_interval=2):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "inputs").mkdir(exist_ok=True)
        self.path = self.directory / "session.json"
        self.lock = threading.RLock()
        self.rows = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        self.api_base, self.key, self.quota = api_base, key, None
        self.stop = threading.Event()
        self.active = False
        self.poll_interval = poll_interval
        self.worker = None
        self.message = ""
        for row in self.rows:
            # A process interruption between sending and receiving must not cause another paid submission.
            if row["status"] == "submitting":
                row.update(status="submission_unknown", error="Check account task history before submitting this image again.")
        self.save()

    def save(self):
        with self.lock:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.rows, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.path)

    def snapshot(self):
        with self.lock:
            return {"rows": [dict(row) for row in self.rows], "active": self.active,
                    "key_configured": bool(self.key), "quota": self.quota, "message": self.message}

    def add(self, name, data):
        if not data or len(data) > MAX_IMAGE:
            raise ValueError("Each image must be between 1 byte and 20 MB.")
        extension, mime = image_type(data)
        identifier = hashlib.sha256(data).hexdigest()[:32]
        with self.lock:
            if any(row["id"] == identifier for row in self.rows):
                return identifier
            if len(self.rows) >= 200:
                raise ValueError("This review session already contains 200 images.")
            name = name.replace("\\", "/").split("/")[-1]
            name = re.sub(r"[\x00-\x1f]", " ", name)[:180] or "image" + extension
            (self.directory / "inputs" / (identifier + extension)).write_bytes(data)
            self.rows.append(dict(id=identifier, filename=name, extension=extension, mime=mime, demo=False,
                                  status="ready", task_id="", ai_reading="", confirmed_reading="",
                                  reviewed=False, note="", error="", result_source=""))
            self.save()
        return identifier

    def demo(self):
        with self.lock:
            for index, value in enumerate(["00123.450", "", "00840"]):
                identifier = "demo-" + str(index + 1)
                if any(row["id"] == identifier for row in self.rows):
                    continue
                self.rows.append(dict(id=identifier, filename=identifier + ".svg", extension=".svg", mime="image/svg+xml",
                                      demo=True, status="accepted" if value else "unreadable", task_id="",
                                      ai_reading=value, confirmed_reading="", reviewed=False, note="",
                                      error="Illustrative unreadable example" if not value else "", result_source="demo"))
            self.save()

    def configure(self, key):
        api = PublicApi(self.api_base, key)
        response = api.request("/api/open/quota")
        with self.lock:
            self.key, self.quota = key, response.get("quota", {})

    def review(self, identifier, value, reviewed, note):
        if value and not re.fullmatch(r"\d+(?:\.\d+)?", value):
            raise ValueError("A confirmed reading must contain digits and an optional decimal point.")
        if reviewed and not value:
            raise ValueError("Enter a reading before confirming it.")
        with self.lock:
            row = next((r for r in self.rows if r["id"] == identifier), None)
            if row is None:
                raise ValueError("Image not found.")
            row.update(confirmed_reading=value, reviewed=bool(reviewed), note=str(note)[:2000])
            self.save()

    def export(self):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["filename", "ai_reading", "confirmed_reading", "selected_reading", "status", "reviewed", "result_source", "note"])
        for row in self.snapshot()["rows"]:
            selected = row["confirmed_reading"] if row["reviewed"] else row["ai_reading"]
            writer.writerow([spreadsheet_text(v) for v in [row["filename"], row["ai_reading"], row["confirmed_reading"],
                             selected, row["status"], "yes" if row["reviewed"] else "no", row["result_source"], row["note"]]])
        return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")

    def start(self):
        with self.lock:
            if self.active:
                return
            if not self.key:
                raise ValueError("Connect an API key before processing your own images.")
            PublicApi(self.api_base, self.key)
            self.active = True
            self.stop.clear()
            self.worker = threading.Thread(target=self.process, args=(list(self.rows),), daemon=True)
            self.worker.start()

    def process(self, rows):
        api = PublicApi(self.api_base, self.key)
        try:
            for row in rows:
                if self.stop.is_set():
                    break
                if row["demo"] or row["status"] in TERMINAL:
                    continue
                try:
                    if not row["task_id"]:
                        row.update(status="submitting", error="")
                        self.save()
                        row["task_id"] = api.submit(row, (self.directory / "inputs" / (row["id"] + row["extension"])).read_bytes())
                        row["status"] = "queued"
                        self.save()
                    while not self.stop.is_set():
                        try:
                            payload = api.request("/api/open/tasks/" + row["task_id"])
                        except ApiError as error:
                            if error.status == 429:
                                self.stop.wait(error.retry_after)
                                continue
                            raise
                        status = payload.get("status")
                        row.update(status=status if status in {"queued", "running", "waiting_ai"} else "running", error="")
                        if status in {"done", "failed", "canceled"}:
                            reading = final_reading(payload) if status == "done" else ""
                            row.update(ai_reading=reading, status="accepted" if reading else ("unreadable" if status == "done" else "failed"),
                                       error="" if reading else "No accepted reading returned; review the image.", result_source=str(payload.get("result_source", "")))
                            self.save()
                            break
                        self.save()
                        self.stop.wait(self.poll_interval)
                except ApiError as error:
                    if not row["task_id"]:
                        # Only an explicit rejection proves a submission was not accepted.
                        row["status"] = "ready" if error.status in {400, 401, 403, 409, 413, 415, 422, 429} else "submission_unknown"
                    row["error"] = str(error)
                    self.message = str(error)
                    self.save()
                    break
                except (OSError, ValueError):
                    row.update(status="submission_unknown" if not row["task_id"] else "failed", error="Local processing interrupted; check the saved task before continuing.")
                    self.save()
                    break
        finally:
            with self.lock:
                self.active = False


class ClientServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, store):
        self.store, self.token = store, secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), ClientHandler)
        self.origin = "http://127.0.0.1:" + str(self.server_port)


class ClientHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, data, mime="application/json; charset=utf-8", extra=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, value in {"Content-Type": mime, "Content-Length": str(len(data)), "Cache-Control": "no-store",
                            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cross-Origin-Resource-Policy": "same-origin",
                            "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'", **(extra or {})}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def allowed(self, private=False):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            self.send(403, {"error": "Invalid local host."})
            return False
        if self.headers.get("Origin") not in {None, self.server.origin}:
            self.send(403, {"error": "Cross-origin access denied."})
            return False
        if private and not secrets.compare_digest(self.headers.get("X-Client-Token", ""), self.server.token):
            self.send(403, {"error": "Refresh this local page before continuing."})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path == "/":
            data = (ASSETS / "index.html").read_text(encoding="utf-8").replace("__CLIENT_TOKEN__", self.server.token)
            return self.send(200, data.encode(), "text/html; charset=utf-8")
        if path in {"/app.js", "/style.css"}:
            return self.send(200, (ASSETS / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith("js") else "text/css; charset=utf-8")
        if path.startswith("/images/"):
            identifier = path.split("/")[-1]
            row = next((r for r in self.server.store.snapshot()["rows"] if r["id"] == identifier), None)
            if row:
                if row["demo"]:
                    reading = row["ai_reading"] or "? ? ? ? ?"
                    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420"><rect width="640" height="420" fill="#e9f0f5"/><circle cx="320" cy="215" r="168" fill="white" stroke="#264c67" stroke-width="14"/><text x="320" y="140" text-anchor="middle" font-family="sans-serif" font-size="24" fill="#264c67">WATER METER · DEMO</text><rect x="174" y="185" width="292" height="64" rx="6" fill="#132b3e"/><text x="320" y="230" text-anchor="middle" font-family="monospace" font-size="38" fill="white">{html.escape(reading)}</text><text x="320" y="300" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#526675">Illustration · saved demo result</text></svg>'
                    return self.send(200, svg.encode(), "image/svg+xml")
                return self.send(200, (self.server.store.directory / "inputs" / (identifier + row["extension"])).read_bytes(), row["mime"])
        if path in {"/local/state", "/local/export"}:
            if not self.allowed(private=True):
                return
            if path.endswith("state"):
                return self.send(200, self.server.store.snapshot())
            return self.send(200, self.server.store.export(), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="watermeter-readings.csv"'})
        self.send(404, {"error": "Not found."})

    def do_POST(self):
        if not self.allowed(private=True):
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_IMAGE:
                return self.send(413, {"error": "Invalid request size."})
            path = urlsplit(self.path).path
            body = self.rfile.read(size)
            store = self.server.store
            if path == "/local/import":
                identifier = store.add(unquote(self.headers.get("X-Filename", "image")), body)
                return self.send(200, {"id": identifier})
            if self.headers.get_content_type() != "application/json":
                return self.send(415, {"error": "Send JSON."})
            value = json.loads(body)
            if path == "/local/demo":
                store.demo()
            elif path == "/local/configure":
                if store.active:
                    raise ValueError("Pause processing before changing the API key.")
                store.configure(str(value.get("key", "")).strip())
            elif path == "/local/run":
                store.start()
            elif path == "/local/pause":
                store.stop.set()
            elif path == "/local/review":
                store.review(str(value.get("id", "")), str(value.get("reading", "")).strip(), value.get("reviewed", False), value.get("note", ""))
            else:
                return self.send(404, {"error": "Not found."})
            self.send(200, {"ok": True})
        except (ValueError, KeyError, TypeError) as error:
            self.send(400, {"error": str(error)[:220]})
        except ApiError as error:
            self.send(502, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description="Run the local WaterMeter image review client.")
    parser.add_argument("--port", type=int, default=0)
    default_data = os.environ.get("WATERMETER_CLIENT_DATA_DIR", str(Path.home() / ".watermeter-image-to-csv"))
    parser.add_argument("--data-dir", type=Path, default=Path(default_data))
    parser.add_argument("--api-base", default=os.environ.get("WATERMETER_API_BASE", "https://watermeterai.com"))
    args = parser.parse_args()
    store = ReviewStore(args.data_dir, args.api_base, os.environ.get("WATERMETER_API_KEY", ""))
    server = ClientServer(args.port, store)
    print("WaterMeter Image-to-CSV: " + server.origin, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        store.stop.set()
        server.server_close()
