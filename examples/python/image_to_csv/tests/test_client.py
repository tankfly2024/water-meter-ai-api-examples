import base64
import csv
import io
import json
import re
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from client import ApiError, ClientServer, PublicApi, ReviewStore, final_reading

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class FakeApi(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.gets += 1
        if self.path.endswith("quota"):
            if self.headers.get("Authorization") != "Bearer test-key":
                return self.send(401, {})
            used = 3 + self.server.posts
            return self.send(200, {"quota": {"account_type": "free", "daily_limit": 20, "used": used, "remaining": 20-used}})
        if self.server.mode == "waiting":
            return self.send(200, {"status": "waiting_ai"})
        if self.server.mode == "rate" and not self.server.rate_sent:
            self.server.rate_sent = True
            return self.send(429, {})
        payload = {"status": "done", "final_reading": "00123.450", "success": "yes", "result_source": "fresh"}
        if self.server.mode == "quality":
            payload["result_summary"] = {"quality": {"status": "review_required"}}
        if self.server.mode == "failed":
            payload.update(status="failed", final_reading="99999")
        self.send(200, payload)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.posts += 1
        if self.server.mode == "truncated":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "500")
            self.end_headers()
            self.wfile.write(b'{"task')
            self.close_connection = True
            return
        if self.server.mode == "unknown":
            self.close_connection = True
            return
        if self.server.mode == "reject":
            return self.send(429, {})
        if self.server.mode == "invalid":
            return self.send(200, {})
        self.send(200, {"task_id": "test-task-" + str(self.server.posts)})


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wmeter-client-test-")
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
        self.fake.mode, self.fake.posts, self.fake.gets, self.fake.rate_sent = "accepted", 0, 0, False
        self.thread = threading.Thread(target=self.fake.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.fake.server_port)
        self.store = ReviewStore(self.temp.name, self.base, poll_interval=0.01)
        self.client = None

    def tearDown(self):
        self.store.stop.set()
        if self.store.worker:
            self.store.worker.join(3)
        if self.client:
            self.client.shutdown()
            self.client.server_close()
        self.fake.shutdown()
        self.fake.server_close()
        target = Path(self.temp.name).resolve()
        self.assertEqual(target.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(target.name.startswith("wmeter-client-test-"))
        self.temp.cleanup()

    def run_image(self, mode="accepted"):
        self.fake.mode = mode
        identifier = self.store.add("water-meter.png", PNG)
        self.store.configure("test-key")
        self.store.start()
        self.store.worker.join(4)
        self.assertFalse(self.store.active)
        return next(r for r in self.store.rows if r["id"] == identifier)

    def test_import_process_review_export_preserves_ai_and_leading_zeros(self):
        row = self.run_image()
        self.assertEqual(row["ai_reading"], "00123.450")
        self.store.review(row["id"], "00123.451", True, "checked against image")
        exported = list(csv.DictReader(io.StringIO(self.store.export().decode("utf-8-sig"))))
        self.assertEqual(exported[0]["ai_reading"], "00123.450")
        self.assertEqual(exported[0]["selected_reading"], "00123.451")
        self.assertEqual(exported[0]["reviewed"], "yes")
        self.assertEqual(self.fake.posts, 1)
        self.assertEqual(self.store.snapshot()["quota"], {"account_type": "free", "daily_limit": 20, "used": 4, "remaining": 16})
        self.assertNotIn("test-key", self.store.path.read_text())
        self.assertNotIn("test-key", json.dumps(self.store.snapshot()))

    def test_duplicate_import_does_not_duplicate_a_paid_submission(self):
        first = self.store.add("a.png", PNG)
        self.assertEqual(first, self.store.add("renamed.png", PNG))
        self.assertEqual(len(self.store.rows), 1)

    def test_unreadable_and_failure_keep_rows_without_recovering_diagnostics(self):
        row = self.run_image("quality")
        self.assertEqual(row["status"], "unreadable")
        self.assertEqual(row["ai_reading"], "")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(self.store.export().decode("utf-8-sig"))))), 1)
        self.assertEqual(final_reading({"success": "no", "final_reading": "999"}), "")
        self.assertEqual(final_reading({"final_reading": 0}), "0")

    def test_failed_task_does_not_export_its_partial_number(self):
        row = self.run_image("failed")
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["ai_reading"], "")

    def test_unknown_submission_is_never_automatically_sent_again(self):
        row = self.run_image("unknown")
        self.assertEqual(row["status"], "submission_unknown")
        self.store.start()
        self.store.worker.join(2)
        self.assertEqual(self.fake.posts, 1)

    def test_missing_task_id_also_blocks_resubmission(self):
        row = self.run_image("invalid")
        self.assertEqual(row["status"], "submission_unknown")
        self.store.start()
        self.store.worker.join(2)
        self.assertEqual(self.fake.posts, 1)

    def test_truncated_upload_response_does_not_allow_duplicate_submission(self):
        row = self.run_image("truncated")
        self.assertEqual(row["status"], "submission_unknown")
        self.store.start()
        self.store.worker.join(2)
        self.assertEqual(self.fake.posts, 1)

    def test_explicit_rejection_does_not_spin_retry(self):
        row = self.run_image("reject")
        self.assertEqual(row["status"], "ready")
        self.assertEqual(self.fake.posts, 1)

    def test_pause_restart_resume_polls_existing_task_without_resubmission(self):
        self.fake.mode = "waiting"
        self.store.add("a.png", PNG)
        self.store.configure("test-key")
        self.store.start()
        deadline = time.monotonic() + 3
        while self.store.rows[0]["status"] != "waiting_ai" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.store.stop.set()
        self.store.worker.join(2)
        self.assertTrue(self.store.rows[0]["task_id"])
        self.fake.mode = "accepted"
        self.store = ReviewStore(self.temp.name, self.base, "test-key", poll_interval=0.01)
        self.store.start()
        self.store.worker.join(3)
        self.assertEqual(self.store.rows[0]["status"], "accepted")
        self.assertEqual(self.fake.posts, 1)

    def test_process_crash_during_submit_requires_history_check(self):
        self.store.add("a.png", PNG)
        self.store.rows[0]["status"] = "submitting"
        self.store.save()
        reloaded = ReviewStore(self.temp.name)
        self.assertEqual(reloaded.rows[0]["status"], "submission_unknown")

    def test_images_imported_after_start_wait_for_the_next_manual_run(self):
        self.fake.mode = "waiting"
        self.store.add("first.png", PNG)
        self.store.configure("test-key")
        self.store.start()
        deadline = time.monotonic() + 3
        while self.store.rows[0]["status"] != "waiting_ai" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.store.add("later.png", PNG + b"later")
        self.fake.mode = "accepted"
        self.store.worker.join(3)
        self.assertFalse(self.store.active)
        self.assertEqual(self.fake.posts, 1)
        self.assertEqual(self.store.rows[1]["status"], "ready")

    def test_poll_rate_limit_waits_without_a_new_submission(self):
        self.assertEqual(self.run_image("rate")["status"], "accepted")
        self.assertTrue(self.fake.rate_sent)
        self.assertEqual(self.fake.posts, 1)

    def test_demo_is_offline_and_unreadable_rows_are_exported(self):
        self.store.demo()
        self.store.demo()
        self.assertEqual(len(self.store.rows), 3)
        self.assertEqual(self.fake.posts, 0)
        self.assertEqual(self.fake.gets, 0)
        rows = list(csv.DictReader(io.StringIO(self.store.export().decode("utf-8-sig"))))
        self.assertEqual(len(rows), 3)
        self.assertTrue(any(r["status"] == "unreadable" and r["selected_reading"] == "" for r in rows))

    def test_csv_formula_injection_and_invalid_reviews_are_blocked(self):
        identifier = self.store.add("=formula.png", PNG)
        self.store.review(identifier, "0", True, "=1+1")
        row = list(csv.DictReader(io.StringIO(self.store.export().decode("utf-8-sig"))))[0]
        self.assertEqual(row["filename"], "'=formula.png")
        self.assertEqual(row["note"], "'=1+1")
        self.assertEqual(row["selected_reading"], "0")
        with self.assertRaises(ValueError):
            self.store.review(identifier, "", True, "")
        with self.assertRaises(ValueError):
            self.store.review(identifier, "=1+1", True, "")

    def test_file_types_and_remote_api_base_validation(self):
        with self.assertRaises(ValueError):
            self.store.add("fake.png", b"<script>alert(1)</script>")
        for address in ["http://example.com", "https://name:secret@example.com", "https://example.com/?key=secret"]:
            with self.assertRaises(ValueError):
                PublicApi(address, "test-key")

    def test_local_http_workflow_and_cross_origin_protection(self):
        self.client = ClientServer(0, self.store)
        threading.Thread(target=self.client.serve_forever, daemon=True).start()
        root = self.client.origin
        page = urlopen(root).read().decode()
        token = re.search(r'name="client-token" content="([^"]+)"', page).group(1)
        def request(path, payload, **headers):
            return urlopen(Request(root+path, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json", "X-Client-Token":token, **headers}))
        with self.assertRaises(HTTPError) as blocked:
            request("/local/demo", {}, Origin="https://example.com")
        self.assertEqual(blocked.exception.code, 403)
        with self.assertRaises(HTTPError):
            urlopen(root+"/local/state")
        request("/local/demo", {}).close()
        result = json.load(urlopen(Request(root+"/local/state", headers={"X-Client-Token":token})))
        self.assertEqual(len(result["rows"]), 3)
        self.assertNotIn("key", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
