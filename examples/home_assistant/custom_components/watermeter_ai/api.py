"""Public HTTP API transport. Blocking network I/O always runs in an executor."""
import asyncio
import json
import re
import secrets
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .const import API_BASE


class ApiError(Exception):
    def __init__(self, status=0, retry_after=2):
        super().__init__("API authentication failed" if status == 401 else "API request failed" + (" (HTTP " + str(status) + ")" if status else ""))
        self.status = status
        self.retry_after = retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def image_type(content):
    if not content or len(content) > 20 * 1024 * 1024:
        raise ValueError("Image must be between 1 byte and 20 MB")
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise ValueError("Camera must provide JPEG, PNG, or WEBP")


class WaterMeterApi:
    def __init__(self, key, executor=None, base=API_BASE):
        url = urlsplit(base)
        if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("HTTPS is required for remote APIs")
        if not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("Invalid API base")
        if not key or any(c in key for c in "\r\n"):
            raise ValueError("Invalid API key")
        self.key, self.base = key, base.rstrip("/")
        self.executor = executor or asyncio.to_thread

    def _request(self, path, body=None, content_type=None):
        headers = {"Authorization": "Bearer " + self.key, "User-Agent": "WaterMeter-HomeAssistant/0.1"}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(self.base + path, data=body, headers=headers)
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                value = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except HTTPError as error:
            retry = error.headers.get("Retry-After", "2")
            error.close()
            raise ApiError(error.code, min(120, max(1, int(retry))) if retry.isdigit() else 2) from None
        except (OSError, URLError, HTTPException, ValueError, UnicodeError):
            # Do not include request headers, provider payloads, or credentials in exceptions.
            raise ApiError() from None

    async def quota(self):
        value = await self.executor(self._request, "/api/open/quota")
        quota = value.get("quota")
        if not isinstance(quota, dict):
            raise ApiError()
        fields = {"account_type", "daily_limit", "used", "remaining", "monthly_remaining", "monthly_bonus_remaining", "fixed_remaining", "is_unlimited"}
        return {k: v for k, v in quota.items() if k in fields and isinstance(v, (str, int, float, bool))}

    async def submit(self, image):
        mime, extension = image_type(image)
        boundary = "watermeter" + secrets.token_hex(16)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="meter{extension}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                + image + f"\r\n--{boundary}--\r\n".encode())
        result = await self.executor(self._request, "/api/open/tasks", body, "multipart/form-data; boundary=" + boundary)
        task_id = result.get("task_id")
        if not isinstance(task_id, (str, int)) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", str(task_id)):
            raise ApiError()
        return str(task_id)

    async def task(self, task_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", task_id):
            raise ValueError("Invalid task identifier")
        return await self.executor(self._request, "/api/open/tasks/" + task_id)
