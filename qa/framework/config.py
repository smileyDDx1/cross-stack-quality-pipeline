from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    base_url: str
    request_timeout: float
    startup_timeout: float

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            base_url=os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/"),
            request_timeout=float(os.getenv("API_TIMEOUT_SECONDS", "10")),
            startup_timeout=float(os.getenv("API_STARTUP_TIMEOUT_SECONDS", "90")),
        )


@lru_cache(maxsize=1)
def run_id() -> str:
    """Identifier stamped into every piece of test data this process creates.

    RUN_ID is set per CI run; the xdist worker id keeps parallel workers apart, and the random
    part keeps two local runs apart even when RUN_ID is not set.
    """
    base = os.getenv("RUN_ID", "local")
    worker = os.getenv("PYTEST_XDIST_WORKER", "main")
    return f"{base}-{worker}-{uuid.uuid4().hex[:6]}"
