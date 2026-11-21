"""Real loopback HTTP transport tests; no requests to the production service."""
import asyncio
import importlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import types
import unittest

sys.dont_write_bytecode = True
COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "watermeter_ai"
package = types.ModuleType("watermeter_standalone")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault(package.__name__, package)
module = importlib.import_module("watermeter_standalone.api")
WaterMeterApi, ApiError = module.WaterMeterApi, module.ApiError


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        self.server.calls.append((self.command, self.path, self.headers.get("Authorization"),
                                  self.rfile.read(int(self.headers.get("Content-Length", 0)))))
        mode = self.server.mode
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-follow")
            self.end_headers()
            return
        if mode == "denied":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"provider-private-diagnostic")
            return
        if mode == "limited":
            self.send_response(429)
            self.send_header("Retry-After", "6")
            self.end_headers()
            return
        if mode == "truncated":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"task_id":')
            return
        if mode == "bad_id":
            result = {"task_id": "../private"}
        elif mode == "list":
            result = []
        elif self.path.endswith("/quota"):
            result = {"quota": {"account_type": "free", "daily_limit": 20, "used": 2, "remaining": 18,
                                "email": "private@example.invalid", "api_key": "fixture-key", "unexpected": {"nested": 1}}}
        elif self.command == "POST":
            result = {"task_id": "ha-task-1"}
        else:
            result = {"status": "done", "final_reading": "12.30"}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=lambda: cls.server.serve_forever(poll_interval=0.02), daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    async def asyncSetUp(self):
        self.server.mode = "normal"
        self.server.calls = []
        self.api = WaterMeterApi("fixture-key", base="http://127.0.0.1:" + str(self.server.server_port))

    async def test_quota_whitelist_and_authentication(self):
        quota = await self.api.quota()
        self.assertEqual(quota, {"account_type": "free", "daily_limit": 20, "used": 2, "remaining": 18})
        self.assertEqual(self.server.calls[0][:3], ("GET", "/api/open/quota", "Bearer fixture-key"))

    async def test_multipart_upload_and_result_query(self):
        image = b"\xff\xd8\xfffixture"
        task_id = await self.api.submit(image)
        result = await self.api.task(task_id)
        self.assertEqual(result["final_reading"], "12.30")
        self.assertEqual(self.server.calls[0][:2], ("POST", "/api/open/tasks"))
        self.assertIn(b'name="file"', self.server.calls[0][3])
        self.assertIn(b"Content-Type: image/jpeg", self.server.calls[0][3])
        self.assertIn(image, self.server.calls[0][3])
        self.assertEqual(self.server.calls[1][:2], ("GET", "/api/open/tasks/ha-task-1"))

    async def test_auth_error_has_no_credentials_or_provider_body(self):
        self.server.mode = "denied"
        with self.assertRaises(ApiError) as caught:
            await self.api.quota()
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("fixture-key", str(caught.exception))
        self.assertNotIn("provider-private", str(caught.exception))

    async def test_redirect_is_never_followed(self):
        self.server.mode = "redirect"
        with self.assertRaises(ApiError) as caught:
            await self.api.quota()
        self.assertEqual(caught.exception.status, 302)
        self.assertEqual(len(self.server.calls), 1)

    async def test_retry_after_is_preserved(self):
        self.server.mode = "limited"
        with self.assertRaises(ApiError) as caught:
            await self.api.quota()
        self.assertEqual(caught.exception.retry_after, 6)

    async def test_truncated_upload_response_is_uncertain_and_not_repeated(self):
        self.server.mode = "truncated"
        with self.assertRaises(ApiError) as caught:
            await self.api.submit(b"\xff\xd8\xfffixture")
        self.assertEqual(caught.exception.status, 0)
        self.assertEqual(len(self.server.calls), 1)

    async def test_invalid_task_identifier_never_reaches_network(self):
        with self.assertRaises(ValueError):
            await self.api.task("../private")
        self.assertEqual(self.server.calls, [])
        self.server.mode = "bad_id"
        with self.assertRaises(ApiError):
            await self.api.submit(b"\xff\xd8\xfffixture")

    async def test_non_object_response_is_rejected(self):
        self.server.mode = "list"
        with self.assertRaises(ApiError):
            await self.api.quota()

    async def test_invalid_key_base_and_image_do_not_make_requests(self):
        for base in ["http://example.invalid", "https://user:secret@example.invalid", "https://example.invalid/private", "https://example.invalid?q=1"]:
            with self.subTest(base=base), self.assertRaises(ValueError):
                WaterMeterApi("fixture-key", base=base)
        with self.assertRaises(ValueError):
            WaterMeterApi("bad\r\nheader")
        with self.assertRaises(ValueError):
            await self.api.submit(b"not an image")
        self.assertEqual(self.server.calls, [])


if __name__ == "__main__":
    unittest.main()
