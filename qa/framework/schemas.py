"""Response contracts. extra="forbid" makes an unannounced new or renamed field fail the suite instead of slipping by."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

import requests
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Status = Literal["todo", "in_progress", "done", "cancelled"]
Priority = Literal["low", "medium", "high"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True, frozen=True)


class User(ApiModel):
    id: UUID
    email: str
    display_name: str
    created_at: datetime


class Token(ApiModel):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int


class Project(ApiModel):
    id: UUID
    name: str
    description: str | None
    task_count: int
    open_task_count: int
    created_at: datetime
    updated_at: datetime


class Task(ApiModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: Status
    priority: Priority
    due_date: date | None
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(ApiModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class Problem(BaseModel):
    """RFC 7807 problem details. Extra members (traceId, allowedStatuses, ...) are allowed by the RFC."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    title: str
    status: int
    detail: str | None = None
    errors: dict[str, list[str]] | None = None


M = TypeVar("M", bound=BaseModel)


def parse(model: type[M], response: requests.Response) -> M:
    return model.model_validate(response.json())
