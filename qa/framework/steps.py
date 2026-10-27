"""Happy-path building blocks for arranging test state through the API (used by API and UI tests alike)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from framework import factories
from framework.assertions import expect_status
from framework.clients import ApiClient
from framework.schemas import Project, Task, Token, User, parse


@dataclass(frozen=True)
class Account:
    user: User
    email: str
    password: str
    token: str


def register_and_login(api: ApiClient, **overrides: Any) -> Account:
    payload = factories.user_payload(**overrides)
    user = parse(User, expect_status(api.auth.register(payload), 201))
    token = parse(Token, expect_status(api.auth.login(payload["email"], payload["password"]), 200))
    return Account(user=user, email=payload["email"], password=payload["password"], token=token.access_token)


def create_project(client: ApiClient, **overrides: Any) -> Project:
    return parse(Project, expect_status(client.projects.create(factories.project_payload(**overrides)), 201))


def create_task(client: ApiClient, project_id: UUID, **overrides: Any) -> Task:
    return parse(Task, expect_status(client.tasks.create(project_id, factories.task_payload(**overrides)), 201))


def move_task(client: ApiClient, task_id: UUID, *statuses: str) -> Task:
    task = None
    for status in statuses:
        task = parse(Task, expect_status(client.tasks.change_status(task_id, status), 200))
    assert task is not None, "move_task needs at least one status"
    return task
