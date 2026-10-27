from __future__ import annotations

import requests

from framework.schemas import Problem


def expect_status(response: requests.Response, expected: int) -> requests.Response:
    if response.status_code != expected:
        raise AssertionError(
            f"Expected HTTP {expected} from {response.request.method} {response.url}, "
            f"got {response.status_code}.\nBody: {response.text[:1000]}"
        )
    return response


def expect_problem(response: requests.Response, status: int, *, field: str | None = None) -> Problem:
    """Asserts an RFC 7807 error response, optionally that a specific field failed validation."""
    expect_status(response, status)
    content_type = response.headers.get("Content-Type", "")
    assert content_type.startswith("application/problem+json"), f"Unexpected content type {content_type!r}"
    problem = Problem.model_validate(response.json())
    assert problem.status == status
    if field is not None:
        assert problem.errors and field in problem.errors, (
            f"Expected a validation error for {field!r}, got {problem.errors}"
        )
    return problem
