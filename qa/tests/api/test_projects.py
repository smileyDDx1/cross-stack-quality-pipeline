import uuid

import pytest

from framework import factories
from framework.assertions import expect_problem, expect_status
from framework.schemas import Page, Project, parse
from framework.steps import create_project, create_task, move_task


def test_create_project_returns_contract_and_location(client):
    payload = factories.project_payload()
    response = expect_status(client.projects.create(payload), 201)

    project = parse(Project, response)
    assert project.name == payload["name"]
    assert project.description == payload["description"]
    assert (project.task_count, project.open_task_count) == (0, 0)
    assert project.created_at == project.updated_at
    assert response.headers["Location"].endswith(f"/api/projects/{project.id}")


def test_read_back_matches_create_response(client):
    # Guards the .NET/Postgres timestamp precision mismatch: create and read must serialise identically.
    created = create_project(client)
    fetched = parse(Project, expect_status(client.projects.get(created.id), 200))
    assert fetched == created


def test_names_are_trimmed_and_blank_description_becomes_null(client):
    name = factories.unique("Padded")
    project = create_project(client, name=f"  {name}  ", description="  ")
    assert project.name == name
    assert project.description is None


@pytest.mark.parametrize(
    ("name", "expected_status"),
    [("", 400), ("   ", 400), ("x" * 100, 201), ("x" * 101, 400)],
    ids=["empty", "whitespace", "max-length", "too-long"],
)
def test_project_name_validation(client, name, expected_status):
    response = client.projects.create(factories.project_payload(name=name))
    if expected_status == 400:
        expect_problem(response, 400, field="name")
    else:
        expect_status(response, expected_status)


def test_duplicate_name_conflicts_for_same_owner_only(client, other_client):
    project = create_project(client)
    expect_problem(client.projects.create(factories.project_payload(name=project.name)), 409)
    expect_status(other_client.projects.create(factories.project_payload(name=project.name)), 201)


def test_update_replaces_fields_and_bumps_updated_at(client):
    project = create_project(client)
    payload = factories.project_payload()

    updated = parse(Project, expect_status(client.projects.update(project.id, payload), 200))
    assert (updated.name, updated.description) == (payload["name"], payload["description"])
    assert updated.created_at == project.created_at
    assert updated.updated_at > project.updated_at


def test_update_to_an_existing_name_conflicts(client):
    first, second = create_project(client), create_project(client)
    expect_problem(client.projects.update(second.id, {"name": first.name}), 409)


def test_delete_removes_project_and_its_tasks(client):
    project = create_project(client)
    task = create_task(client, project.id)

    expect_status(client.projects.delete(project.id), 204)
    expect_problem(client.projects.get(project.id), 404)
    expect_problem(client.tasks.get(task.id), 404)
    expect_problem(client.projects.delete(project.id), 404)


def test_unknown_project_is_404(client):
    expect_problem(client.projects.get(uuid.uuid4()), 404)


def test_task_counts_reflect_task_states(client):
    project = create_project(client)
    tasks = [create_task(client, project.id) for _ in range(4)]
    move_task(client, tasks[0].id, "in_progress", "done")
    move_task(client, tasks[1].id, "cancelled")
    move_task(client, tasks[2].id, "in_progress")

    fetched = parse(Project, client.projects.get(project.id))
    assert (fetched.task_count, fetched.open_task_count) == (4, 2)

    listed = parse(Page[Project], client.projects.list())
    assert [(p.task_count, p.open_task_count) for p in listed.items] == [(4, 2)]


def test_pagination_is_stable_and_complete(client):
    created = [create_project(client) for _ in range(5)]

    pages = [parse(Page[Project], expect_status(client.projects.list(page=n, pageSize=2), 200)) for n in (1, 2, 3, 4)]

    assert [len(p.items) for p in pages] == [2, 2, 1, 0]
    assert all(p.total == 5 and p.page_size == 2 for p in pages)
    seen = [project.id for page in pages for project in page.items]
    assert seen == [project.id for project in created], "pages should be in creation order without gaps or repeats"


@pytest.mark.parametrize(
    ("params", "field"),
    [({"page": 0}, "page"), ({"pageSize": 0}, "pageSize"), ({"pageSize": 101}, "pageSize")],
    ids=["page-zero", "size-zero", "size-over-max"],
)
def test_invalid_paging_is_rejected(client, params, field):
    expect_problem(client.projects.list(**params), 400, field=field)
