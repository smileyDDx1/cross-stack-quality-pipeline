"""Test data builders. Every value that must be unique carries the run id, so parallel runs never collide."""

from __future__ import annotations

import uuid
from typing import Any

from framework.config import run_id

DEFAULT_PASSWORD = "Passw0rd!qa"


def unique(prefix: str) -> str:
    return f"{prefix}-{run_id()}-{uuid.uuid4().hex[:8]}"


def user_payload(**overrides: Any) -> dict[str, Any]:
    token = unique("qa")
    return {
        "email": f"{token}@example.test",
        "password": DEFAULT_PASSWORD,
        "displayName": f"QA {token[-8:]}",
        **overrides,
    }


def project_payload(**overrides: Any) -> dict[str, Any]:
    return {"name": unique("Project"), "description": "Created by the automated test suite", **overrides}


def task_payload(**overrides: Any) -> dict[str, Any]:
    return {"title": unique("Task"), "priority": "medium", **overrides}
