from __future__ import annotations

import json
import time
from collections import deque
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from framework.config import Settings

_SENSITIVE_FIELDS = {"password", "accessToken"}
_MAX_BODY_CHARS = 1500


class TrafficLog:
    """Keeps the last few HTTP exchanges so a failing test can show exactly what was sent and received."""

    def __init__(self, maxlen: int = 15) -> None:
        self._entries: deque[str] = deque(maxlen=maxlen)

    def record(self, response: requests.Response, elapsed_ms: float) -> None:
        request = response.request
        lines = [
            f"--> {request.method} {request.url}",
            *([_redact(request.body)] if request.body else []),
            f"<-- {response.status_code} {response.reason} ({elapsed_ms:.0f} ms)",
            *([_redact(response.text)] if response.text else []),
        ]
        self._entries.append("\n".join(lines))

    def clear(self) -> None:
        self._entries.clear()

    def dump(self) -> str:
        return "\n\n".join(self._entries)


traffic = TrafficLog()


def _redact(body: Any) -> str:
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return str(body)[:_MAX_BODY_CHARS]
    if isinstance(data, dict):
        data = {k: ("***" if k in _SENSITIVE_FIELDS else v) for k, v in data.items()}
    return json.dumps(data, indent=2)[:_MAX_BODY_CHARS]


class ApiSession:
    """Thin wrapper over requests.Session: base URL, default timeout, bearer auth and traffic logging.

    Only connection errors are retried. Retrying on 5xx would hide exactly the failures the suite exists to catch.
    """

    def __init__(self, settings: Settings, token: str | None = None) -> None:
        self.settings = settings
        self.token = token
        self._session = requests.Session()
        retry = Retry(total=3, connect=3, read=0, status=0, other=0, backoff_factor=0.3)
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._session.headers["Accept"] = "application/json"
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    def with_token(self, token: str | None) -> ApiSession:
        return ApiSession(self.settings, token)

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.settings.request_timeout)
        started = time.perf_counter()
        response = self._session.request(method, f"{self.settings.base_url}{path}", **kwargs)
        traffic.record(response, (time.perf_counter() - started) * 1000)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)


def wait_until_healthy(settings: Settings) -> None:
    deadline = time.monotonic() + settings.startup_timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{settings.base_url}/health", timeout=3)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(
        f"API at {settings.base_url} not healthy after {settings.startup_timeout:.0f}s ({last_error}). "
        "Start it with: docker compose up --build --detach --wait"
    )
