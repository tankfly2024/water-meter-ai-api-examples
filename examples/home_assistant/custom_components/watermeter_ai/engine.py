"""Framework-independent state machine; no camera or cloud calls on startup."""
import asyncio
import hashlib
import math
import re
from datetime import datetime, timezone
from decimal import Decimal

from .api import ApiError, image_type


class ReadError(Exception):
    pass


def reading_from(payload):
    summary = payload.get("result_summary")
    summary = summary if isinstance(summary, dict) else {}
    quality = summary.get("quality") or payload.get("quality")
    quality = quality if isinstance(quality, dict) else {}
    if payload.get("success") == "no" or summary.get("success") == "no" or quality.get("status") in {"review_required", "unreadable"}:
        return None
    value = payload.get("final_reading")
    value = str(value) if value is not None else ""
    return value if re.fullmatch(r"\d+(?:\.\d+)?", value) and math.isfinite(float(value)) else None


class ReadEngine:
    def __init__(self, api, save, state=None, max_increase="10", poll_interval=2, poll_timeout=120):
        self.api, self.save = api, save
        self.max_increase = Decimal(str(max_increase))
        if not self.max_increase.is_finite() or self.max_increase <= 0:
            raise ValueError("Maximum increase must be positive")
        self.poll_interval, self.poll_timeout = poll_interval, poll_timeout
        self.lock = asyncio.Lock()
        defaults = dict(total=None, candidate=None, last_ai_reading=None, task_id=None,
                        submitting=False, submission_unknown=False, last_image_hash=None,
                        status="idle", quota={}, quota_error=False, updated_at=None, result_source=None)
        if state:
            defaults.update({k: state[k] for k in defaults if k in state})
        self.state = defaults
        if self.state["submitting"] and not self.state["task_id"]:
            self.state.update(submitting=False, submission_unknown=True, status="submission_unknown")

    async def persist(self):
        await self.save(dict(self.state))

    async def refresh_quota(self):
        try:
            self.state["quota"] = await self.api.quota()
            self.state["quota_error"] = False
        except ApiError:
            self.state["quota_error"] = True
        await self.persist()

    async def read(self, image=None):
        if self.lock.locked():
            raise ReadError("Recognition is already running")
        async with self.lock:
            if self.state["submission_unknown"]:
                raise ReadError("Submission is uncertain. Check website task history before another upload")
            if self.state["candidate"] is not None:
                raise ReadError("Confirm the pending reading before another recognition")
            try:
                if not self.state["task_id"]:
                    image_type(image)
                    digest = hashlib.sha256(image).hexdigest()
                    if digest == self.state["last_image_hash"]:
                        return dict(self.state)
                    self.state.update(submitting=True, status="submitting", last_image_hash=digest)
                    await self.persist()
                    try:
                        task_id = await self.api.submit(image)
                    except ApiError as error:
                        rejected = error.status in {400, 401, 403, 409, 413, 415, 422, 429}
                        self.state.update(submitting=False, submission_unknown=not rejected,
                                          status="error" if rejected else "submission_unknown")
                        if rejected:
                            self.state["last_image_hash"] = None
                        await self.persist()
                        raise
                    self.state.update(task_id=task_id, submitting=False, status="queued")
                    await self.persist()
                deadline = asyncio.get_running_loop().time() + self.poll_timeout
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        result = await self.api.task(self.state["task_id"])
                    except ApiError as error:
                        if error.status == 429:
                            await asyncio.sleep(min(error.retry_after, max(0, deadline-asyncio.get_running_loop().time())))
                            continue
                        self.state["status"] = "error"
                        await self.persist()
                        raise
                    status = result.get("status")
                    if status in {"done", "failed", "canceled"}:
                        self.state.update(task_id=None, updated_at=datetime.now(timezone.utc).isoformat(),
                                          result_source=result.get("result_source"))
                        value = reading_from(result) if status == "done" else None
                        self.state["last_ai_reading"] = value
                        if value is None:
                            self.state.update(status="unreadable" if status == "done" else "error", candidate=None)
                        elif self.state["total"] is None:
                            self.state.update(status="review_required", candidate=value)
                        elif Decimal(value) < Decimal(self.state["total"]):
                            self.state.update(status="backwards", candidate=None)
                        elif Decimal(value)-Decimal(self.state["total"]) > self.max_increase:
                            self.state.update(status="review_required", candidate=value)
                        else:
                            self.state.update(status="accepted", total=value, candidate=None)
                        await self.persist()
                        await self.refresh_quota()
                        return dict(self.state)
                    self.state["status"] = status if status in {"queued", "running", "waiting_ai"} else "running"
                    await self.persist()
                    await asyncio.sleep(self.poll_interval)
                self.state["status"] = "pending"
                await self.persist()
                return dict(self.state)
            except asyncio.CancelledError:
                if self.state["submitting"] and not self.state["task_id"]:
                    self.state.update(submitting=False, submission_unknown=True, status="submission_unknown")
                await self.persist()
                raise

    async def confirm(self):
        if self.lock.locked():
            raise ReadError("Wait for recognition to finish")
        candidate = self.state["candidate"]
        if candidate is None:
            raise ReadError("There is no pending accepted reading to confirm")
        if self.state["total"] is not None and Decimal(candidate) < Decimal(self.state["total"]):
            raise ReadError("A backwards reading cannot reset the meter")
        self.state.update(total=candidate, candidate=None, status="accepted")
        await self.persist()

    async def discard(self):
        if self.lock.locked():
            raise ReadError("Wait for recognition to finish")
        if self.state["candidate"] is None:
            raise ReadError("There is no pending reading to discard")
        self.state.update(candidate=None, status="accepted" if self.state["total"] is not None else "idle")
        await self.persist()
