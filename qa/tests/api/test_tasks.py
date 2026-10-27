import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from framework import factories
from framework.assertions import expect_problem, expect_status
from framework.schemas import Page, Task, parse
from framework.steps import create_project, create_task, move_task


@pytest.fixture
def project(client):
    return create_project(client)


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def test_create_task_applies_defaults(client, project):
    response = expect_status(client.tasks.create(project.id, {"title": factories.unique("Task")}), 201)
    task = parse(Task, response)
    assert (task.status, task.priority, task.due_date, task.description) == ("todo", "medium", None, None)
    assert task.project_id == project.id
    assert response.headers["Location"].endswith(f"/api/tasks/{task.id}")


def test_create_task_with_all_fields(client, project):
    due = utc_today() + timedelta(days=7)
    task = create_task(client, project.id, description="Write the release notes", priority="high", dueDate=due.isoformat())
    assert (task.description, task.priority, task.due_date) == ("Write the release notes", "high", due)
    assert parse(Task, client.tasks.get(task.id)) == task


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"title": ""}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"priority": "urgent"}, "priority"),
        ({"dueDate": (utc_today() - timedelta(days=1)).isoformat()}, "dueDate"),
    ],
    ids=["empty-title", "long-title", "unknown-priority", "past-due-date"],
)
def test_invalid_task_is_rejected(client, project, overrides, field):
    expect_problem(client.tasks.create(project.id, factories.task_payload(**overrides)), 400, field=field)


def test_due_date_today_is_accepted(client, project):
    assert create_task(client, project.id, dueDate=utc_today().isoformat()).due_date == utc_today()


def test_malformed_json_is_a_400_not_a_500(client, project):
    response = client.session.post(
        f"/api/projects/{project.id}/tasks", data="{not json", headers={"Content-Type": "application/json"}
    )
    expect_status(response, 400)


def test_patch_updates_only_the_fields_sent(client, project):
    task = create_task(client, project.id, description="original", priority="low")

    updated = parse(Task, expect_status(client.tasks.update(task.id, {"priority": "high"}), 200))
    assert updated.priority == "high"
    assert (updated.title, updated.description, updated.status) == (task.title, "original", "todo")
    assert updated.updated_at > task.updated_at


def test_task_in_unknown_project_is_404(client):
    expect_problem(client.tasks.create(uuid.uuid4(), factories.task_payload()), 404)


def test_filter_by_status_and_priority(client, project):
    low = create_task(client, project.id, priority="low")
    high_done = create_task(client, project.id, priority="high")
    high_open = create_task(client, project.id, priority="high")
    move_task(client, high_done.id, "in_progress", "done")

    def ids(**params):
        return [t.id for t in parse(Page[Task], expect_status(client.tasks.list(project.id, **params), 200)).items]

    assert ids(priority="high") == [high_done.id, high_open.id]
    assert ids(status="done") == [high_done.id]
    assert ids(status="todo", priority="low") == [low.id]


def test_search_is_case_insensitive_and_treats_wildcards_literally(client, project):
    marker = uuid.uuid4().hex[:8]
    hit = create_task(client, project.id, title=f"Fix login bug {marker}")
    percent = create_task(client, project.id, title=f"Reach 100% coverage {marker}")
    create_task(client, project.id, title="Unrelated chore")

    def search(term):
        return [t.id for t in parse(Page[Task], client.tasks.list(project.id, search=term)).items]

    assert search(f"LOGIN BUG {marker}") == [hit.id]
    assert search(marker) == [hit.id, percent.id]
    assert search("100%") == [percent.id]
    assert search("%") == [percent.id], "'%' must match literally, not as a SQL wildcard"


@pytest.mark.parametrize("params", [{"status": "finished"}, {"priority": "urgent"}], ids=["bad-status", "bad-priority"])
def test_invalid_filters_are_rejected(client, project, params):
    expect_problem(client.tasks.list(project.id, **params), 400, field=next(iter(params)))


def test_delete_task(client, project):
    task = create_task(client, project.id)
    expect_status(client.tasks.delete(task.id), 204)
    expect_problem(client.tasks.get(task.id), 404)
