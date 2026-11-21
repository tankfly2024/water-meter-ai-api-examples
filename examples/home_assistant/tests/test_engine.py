"""Test the real state engine without substituting a fake Home Assistant host."""
import asyncio
import copy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

sys.dont_write_bytecode = True
COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "watermeter_ai"
package = types.ModuleType("watermeter_standalone")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault(package.__name__, package)
api_module = importlib.import_module("watermeter_standalone.api")
engine_module = importlib.import_module("watermeter_standalone.engine")
ApiError, ReadError, ReadEngine = api_module.ApiError, engine_module.ReadError, engine_module.ReadEngine
PNG = b"\x89PNG\r\n\x1a\nfixture"


class FakeApi:
    def __init__(self, results=None):
        self.posts = 0
        self.gets = []
        self.results = results or [{"status": "done", "final_reading": "00100.50", "result_source": "fresh"}]
        self.submit_error = None
        self.quota_error = False
        self.quota_value = {"account_type": "free", "daily_limit": 20, "used": 1, "remaining": 19}

    async def submit(self, image):
        self.posts += 1
        if self.submit_error:
            raise self.submit_error
        return "task-1"

    async def task(self, task_id):
        self.gets.append(task_id)
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result

    async def quota(self):
        if self.quota_error:
            raise ApiError(503)
        return dict(self.quota_value)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    def make_engine(self, api=None, state=None, **kwargs):
        self.saved = []

        async def save(value):
            self.saved.append(copy.deepcopy(value))

        return ReadEngine(api or FakeApi(), save, state=state, poll_interval=0.001, **kwargs)

    async def test_first_read_requires_confirmation_and_preserves_text(self):
        api = FakeApi()
        engine = self.make_engine(api)
        self.assertEqual(api.posts, 0)
        result = await engine.read(PNG)
        self.assertIsNone(result["total"])
        self.assertEqual(result["candidate"], "00100.50")
        self.assertTrue(self.saved[0]["submitting"])
        await engine.confirm()
        self.assertEqual(engine.state["total"], "00100.50")
        self.assertEqual(api.posts, 1)
        self.assertEqual(engine.state["quota"]["remaining"], 19)

    async def test_normal_forward_value_is_accepted(self):
        engine = self.make_engine(state={"total": "100"})
        await engine.read(PNG)
        self.assertEqual(engine.state["total"], "00100.50")
        self.assertIsNone(engine.state["candidate"])

    async def test_zero_is_a_real_reading(self):
        engine = self.make_engine(FakeApi([{"status": "done", "final_reading": "000.00"}]))
        await engine.read(PNG)
        await engine.confirm()
        self.assertEqual(engine.state["total"], "000.00")

    async def test_large_jump_held_and_can_be_discarded(self):
        engine = self.make_engine(state={"total": "20"}, max_increase="10")
        await engine.read(PNG)
        self.assertEqual(engine.state["total"], "20")
        self.assertEqual(engine.state["status"], "review_required")
        with self.assertRaises(ReadError):
            await engine.read(PNG + b"new")
        await engine.discard()
        self.assertEqual(engine.state["total"], "20")
        self.assertIsNone(engine.state["candidate"])
        await engine.read(PNG + b"new")
        await engine.confirm()
        self.assertEqual(engine.state["total"], "00100.50")

    async def test_discard_first_value_does_not_create_zero_baseline(self):
        engine = self.make_engine()
        await engine.read(PNG)
        await engine.discard()
        self.assertIsNone(engine.state["total"])
        with self.assertRaises(ReadError):
            await engine.confirm()

    async def test_backwards_value_cannot_reset_statistics(self):
        engine = self.make_engine(state={"total": "500"})
        await engine.read(PNG)
        self.assertEqual(engine.state["status"], "backwards")
        self.assertEqual(engine.state["total"], "500")
        with self.assertRaises(ReadError):
            await engine.confirm()

    async def test_quality_rejection_and_terminal_failure_keep_total(self):
        cases = [
            {"status": "done", "final_reading": "150", "success": "no"},
            {"status": "done", "final_reading": "150", "result_summary": {"quality": {"status": "review_required"}}},
            {"status": "done", "final_reading": "150", "result_summary": {"quality": {"status": "unreadable"}}},
            {"status": "done", "final_reading": "-"},
            {"status": "failed", "final_reading": "150"},
            {"status": "canceled", "final_reading": "150"},
        ]
        for result in cases:
            with self.subTest(result=result):
                engine = self.make_engine(FakeApi([result]), state={"total": "100"})
                await engine.read(PNG)
                self.assertEqual(engine.state["total"], "100")
                self.assertIsNone(engine.state["candidate"])
                self.assertEqual(engine.state["status"], "unreadable" if result["status"] == "done" else "error")

    async def test_unchanged_snapshot_does_not_upload_again(self):
        api = FakeApi()
        engine = self.make_engine(api, state={"total": "100"})
        await engine.read(PNG)
        await engine.read(PNG)
        self.assertEqual(api.posts, 1)

    async def test_unknown_submission_persists_and_never_auto_retries(self):
        api = FakeApi()
        api.submit_error = ApiError()
        engine = self.make_engine(api)
        with self.assertRaises(ApiError):
            await engine.read(PNG)
        restored = self.make_engine(api, state=copy.deepcopy(engine.state))
        with self.assertRaises(ReadError):
            await restored.read(PNG + b"new")
        self.assertEqual(api.posts, 1)
        self.assertTrue(restored.state["submission_unknown"])

    async def test_explicit_rejection_allows_only_manual_retry(self):
        api = FakeApi()
        api.submit_error = ApiError(429)
        engine = self.make_engine(api)
        with self.assertRaises(ApiError):
            await engine.read(PNG)
        self.assertEqual(api.posts, 1)
        self.assertFalse(engine.state["submission_unknown"])
        api.submit_error = None
        await engine.read(PNG)
        self.assertEqual(api.posts, 2)

    async def test_crashed_upload_restores_as_uncertain(self):
        engine = self.make_engine(state={"submitting": True})
        self.assertTrue(engine.state["submission_unknown"])
        with self.assertRaises(ReadError):
            await engine.read(PNG)

    async def test_timeout_then_restart_resumes_same_task_without_post(self):
        api = FakeApi()
        engine = self.make_engine(api, poll_timeout=0)
        await engine.read(PNG)
        self.assertEqual(engine.state["status"], "pending")
        restored = self.make_engine(api, state=engine.state)
        await restored.read()
        self.assertEqual(api.posts, 1)
        self.assertEqual(api.gets, ["task-1"])
        self.assertEqual(restored.state["candidate"], "00100.50")

    async def test_poll_error_preserves_task(self):
        api = FakeApi([ApiError(503)])
        engine = self.make_engine(api)
        with self.assertRaises(ApiError):
            await engine.read(PNG)
        api.results = [{"status": "done", "final_reading": "5"}]
        await engine.read()
        self.assertEqual(api.posts, 1)
        self.assertEqual(api.gets, ["task-1", "task-1"])

    async def test_poll_rate_limit_retries_get_only(self):
        api = FakeApi([ApiError(429, retry_after=0.001), {"status": "done", "final_reading": "1"}])
        await self.make_engine(api).read(PNG)
        self.assertEqual(api.posts, 1)
        self.assertEqual(len(api.gets), 2)

    async def test_busy_and_canceled_post_are_not_resubmitted(self):
        api = FakeApi()
        entered = asyncio.Event()

        async def blocked_submit(image):
            api.posts += 1
            entered.set()
            await asyncio.Future()

        api.submit = blocked_submit
        engine = self.make_engine(api)
        task = asyncio.create_task(engine.read(PNG))
        await entered.wait()
        with self.assertRaises(ReadError):
            await engine.read(PNG)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(engine.state["submission_unknown"])
        self.assertEqual(api.posts, 1)

    async def test_canceled_poll_keeps_id_for_resume(self):
        api = FakeApi()
        entered = asyncio.Event()

        async def blocked_poll(task_id):
            entered.set()
            await asyncio.Future()

        api.task = blocked_poll
        engine = self.make_engine(api)
        task = asyncio.create_task(engine.read(PNG))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(engine.state["task_id"], "task-1")
        self.assertFalse(engine.state["submission_unknown"])

    async def test_server_custom_quota_is_not_replaced_with_twenty(self):
        api = FakeApi()
        for limit in [0, 7, 20]:
            api.quota_value = {"account_type": "free", "daily_limit": limit, "remaining": limit, "used": 0}
            engine = self.make_engine(api)
            await engine.refresh_quota()
            self.assertEqual(engine.state["quota"]["daily_limit"], limit)
        api.quota_value = {"account_type": "paid", "monthly_remaining": 200}
        await engine.refresh_quota()
        self.assertNotIn("daily_limit", engine.state["quota"])

    async def test_quota_failure_does_not_erase_accepted_reading(self):
        api = FakeApi()
        api.quota_error = True
        engine = self.make_engine(api, state={"total": "100"})
        await engine.read(PNG)
        self.assertEqual(engine.state["total"], "00100.50")
        self.assertTrue(engine.state["quota_error"])

    async def test_bad_image_and_storage_failure_prevent_post(self):
        api = FakeApi()
        engine = self.make_engine(api)
        with self.assertRaises(ValueError):
            await engine.read(b"invalid")

        async def broken_save(state):
            raise OSError("fixture storage unavailable")

        engine.save = broken_save
        with self.assertRaises(OSError):
            await engine.read(PNG)
        self.assertEqual(api.posts, 0)


class MetadataTests(unittest.TestCase):
    def test_invalid_numbers_cannot_enter_statistics(self):
        for value in [None, "-", "NaN", "Infinity", "1e6", "-1", "1,000", "9" * 400]:
            with self.subTest(value=value):
                self.assertIsNone(engine_module.reading_from({"final_reading": value}))

    def test_translations_have_matching_keys(self):
        def keys(value, prefix=""):
            result = set()
            for key, child in value.items():
                path = prefix + "/" + key
                result.add(path)
                if isinstance(child, dict):
                    result.update(keys(child, path))
            return result

        en = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
        translated_en = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
        zh = json.loads((COMPONENT / "translations/zh-Hans.json").read_text(encoding="utf-8"))
        self.assertEqual(en, translated_en)
        self.assertEqual(keys(en), keys(zh))

    def test_manifest_declares_manual_custom_component(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["domain"], "watermeter_ai")
        self.assertEqual(manifest["requirements"], [])
        self.assertIn("camera", manifest["dependencies"])


if __name__ == "__main__":
    unittest.main()
