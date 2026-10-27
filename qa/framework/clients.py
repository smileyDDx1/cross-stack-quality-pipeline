"""Resource clients. They return raw responses so tests can assert on failures as easily as on successes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import requests

from framework.session import ApiSession

Json = dict[str, Any]


class AuthClient:
    def __init__(self, session: ApiSession) -> None:
        self._s = session

    def register(self, payload: Json) -> requests.Response:
        return self._s.post("/api/auth/register", json=payload)

    def login(self, email: str, password: str) -> requests.Response:
        return self._s.post("/api/auth/login", json={"email": email, "password": password})

    def me(self) -> requests.Response:
        return self._s.get("/api/auth/me")

    def delete_me(self) -> requests.Response:
        return self._s.delete("/api/auth/me")


class ProjectClient:
    def __init__(self, session: ApiSession) -> None:
        self._s = session

    def list(self, **params: Any) -> requests.Response:
        return self._s.get("/api/projects", params=params)

    def create(self, payload: Json) -> requests.Response:
        return self._s.post("/api/projects", json=payload)

    def get(self, project_id: UUID | str) -> requests.Response:
        return self._s.get(f"/api/projects/{project_id}")

    def update(self, project_id: UUID | str, payload: Json) -> requests.Response:
        return self._s.put(f"/api/projects/{project_id}", json=payload)

    def delete(self, project_id: UUID | str) -> requests.Response:
        return self._s.delete(f"/api/projects/{project_id}")


class TaskClient:
    def __init__(self, session: ApiSession) -> None:
        self._s = session

    def list(self, project_id: UUID | str, **params: Any) -> requests.Response:
        return self._s.get(f"/api/projects/{project_id}/tasks", params=params)

    def create(self, project_id: UUID | str, payload: Json) -> requests.Response:
        return self._s.post(f"/api/projects/{project_id}/tasks", json=payload)

    def get(self, task_id: UUID | str) -> requests.Response:
        return self._s.get(f"/api/tasks/{task_id}")

    def update(self, task_id: UUID | str, payload: Json) -> requests.Response:
        return self._s.patch(f"/api/tasks/{task_id}", json=payload)

    def change_status(self, task_id: UUID | str, status: str) -> requests.Response:
        return self._s.post(f"/api/tasks/{task_id}/status", json={"status": status})

    def delete(self, task_id: UUID | str) -> requests.Response:
        return self._s.delete(f"/api/tasks/{task_id}")


class ApiClient:
    """Facade over the resource clients, bound to one identity (anonymous or a bearer token)."""

    def __init__(self, session: ApiSession) -> None:
        self.session = session
        self.auth = AuthClient(session)
        self.projects = ProjectClient(session)
        self.tasks = TaskClient(session)

    def as_user(self, token: str | None) -> ApiClient:
        return ApiClient(self.session.with_token(token))
