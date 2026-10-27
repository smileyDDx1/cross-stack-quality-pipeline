"""One user must never see or change another user's data. Foreign ids are reported as 404, not 403."""

from framework import factories
from framework.assertions import expect_problem
from framework.schemas import Page, Project, parse
from framework.steps import create_project, create_task


def test_projects_are_invisible_to_other_users(client, other_client):
    project = create_project(client)

    assert parse(Page[Project], other_client.projects.list()).total == 0
    expect_problem(other_client.projects.get(project.id), 404)
    expect_problem(other_client.projects.update(project.id, factories.project_payload()), 404)
    expect_problem(other_client.projects.delete(project.id), 404)
    expect_problem(other_client.tasks.list(project.id), 404)
    expect_problem(other_client.tasks.create(project.id, factories.task_payload()), 404)


def test_tasks_are_invisible_to_other_users(client, other_client):
    project = create_project(client)
    task = create_task(client, project.id)

    expect_problem(other_client.tasks.get(task.id), 404)
    expect_problem(other_client.tasks.update(task.id, {"title": "hijacked"}), 404)
    expect_problem(other_client.tasks.change_status(task.id, "in_progress"), 404)
    expect_problem(other_client.tasks.delete(task.id), 404)

    # And nothing changed for the owner.
    assert client.tasks.get(task.id).json()["title"] == task.title
