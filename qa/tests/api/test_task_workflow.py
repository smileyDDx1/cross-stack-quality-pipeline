"""Workflow at the API level.

The full transition matrix is unit-tested in TaskTracker.UnitTests. Here we only check what a unit test cannot:
that the rule is enforced over HTTP, persisted, and reported with a usable 409 contract.
"""

from framework.assertions import expect_problem
from framework.schemas import Task, parse
from framework.steps import create_project, create_task, move_task


def test_full_lifecycle_is_persisted(client):
    project = create_project(client)
    task = create_task(client, project.id)

    done = move_task(client, task.id, "in_progress", "done")
    assert done.status == "done"
    assert parse(Task, client.tasks.get(task.id)).status == "done"

    reopened = move_task(client, task.id, "in_progress")
    assert reopened.status == "in_progress"


def test_illegal_transition_is_409_with_allowed_statuses(client):
    project = create_project(client)
    task = create_task(client, project.id)
    move_task(client, task.id, "in_progress", "done")

    problem = expect_problem(client.tasks.change_status(task.id, "todo"), 409)
    assert problem.model_extra["currentStatus"] == "done"
    assert problem.model_extra["allowedStatuses"] == ["in_progress"]
    assert parse(Task, client.tasks.get(task.id)).status == "done", "a rejected transition must not change state"


def test_unknown_status_value_is_400(client):
    project = create_project(client)
    task = create_task(client, project.id)
    expect_problem(client.tasks.change_status(task.id, "finished"), 400, field="status")
