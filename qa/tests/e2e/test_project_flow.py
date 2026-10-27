from datetime import date, timedelta

from playwright.sync_api import Page, expect

from framework import factories
from framework.schemas import Page as ApiPage
from framework.schemas import Project, parse
from framework.steps import create_project, create_task, move_task

from .pages import ProjectsPage


def test_create_project_add_task_and_complete_it(signed_in_page: Page, client):
    projects = ProjectsPage(signed_in_page)
    name = factories.unique("UI project")

    projects.create(name, "Created through the browser")
    expect(projects.card(name)).to_be_visible()

    project_page = projects.open_project(name)
    due = (date.today() + timedelta(days=3)).isoformat()
    row = project_page.add_task("Write the onboarding guide", priority="high", due_date=due)
    expect(row.get_by_test_id("task-priority-badge")).to_have_text("high")
    expect(row.get_by_test_id("task-due")).to_have_text(f"due {due}")

    project_page.move("Write the onboarding guide", "in_progress")
    project_page.move("Write the onboarding guide", "done")
    expect(project_page.row("Write the onboarding guide").get_by_test_id("task-status")).to_have_text("Done")

    project_page.back.click()
    expect(projects.card(name).get_by_test_id("project-counts")).to_have_text("1 task · 0 open")

    # The UI said it worked; confirm the backend agrees.
    [stored] = parse(ApiPage[Project], client.projects.list()).items
    assert (stored.name, stored.task_count, stored.open_task_count) == (name, 1, 0)


def test_api_validation_error_is_shown_inline(signed_in_page: Page):
    projects = ProjectsPage(signed_in_page)
    projects.create("   ")
    expect(projects.error).to_have_text("Name is required.")
    expect(projects.empty_state).to_be_visible()


def test_status_filter_shows_matching_tasks(signed_in_page: Page, client):
    # Arrange through the API: this test is about the filter, not about creating tasks.
    project = create_project(client)
    todo = create_task(client, project.id, title="Still to do")
    done = create_task(client, project.id, title="Already done")
    move_task(client, done.id, "in_progress", "done")

    signed_in_page.reload()
    project_page = ProjectsPage(signed_in_page).open_project(project.name)
    expect(project_page.rows).to_have_count(2)

    project_page.filter_by("done")
    expect(project_page.rows).to_have_count(1)
    expect(project_page.row(done.title)).to_be_visible()

    project_page.filter_by("todo")
    expect(project_page.rows).to_have_count(1)
    expect(project_page.row(todo.title)).to_be_visible()


def test_deleting_a_task_removes_it(signed_in_page: Page, client):
    project = create_project(client)
    task = create_task(client, project.id, title="Delete me")

    signed_in_page.reload()
    project_page = ProjectsPage(signed_in_page).open_project(project.name)
    project_page.delete(task.title)
    expect(signed_in_page.get_by_test_id("tasks-empty")).to_be_visible()
