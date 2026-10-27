"""Page objects. Locators use data-testid so tests survive copy and layout changes."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect


def exact(text: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(text)}\s*$")


class AuthPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.email = page.get_by_test_id("auth-email")
        self.password = page.get_by_test_id("auth-password")
        self.display_name = page.get_by_test_id("auth-display-name")
        self.submit = page.get_by_test_id("auth-submit")
        self.toggle = page.get_by_test_id("auth-toggle")
        self.error = page.get_by_test_id("auth-error")

    def open(self) -> AuthPage:
        self.page.goto("/")
        expect(self.submit).to_be_visible()
        return self

    def sign_in(self, email: str, password: str) -> None:
        self.email.fill(email)
        self.password.fill(password)
        self.submit.click()

    def register(self, email: str, password: str, display_name: str) -> None:
        self.toggle.click()
        expect(self.display_name).to_be_visible()
        self.display_name.fill(display_name)
        self.sign_in(email, password)


class ProjectsPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.name = page.get_by_test_id("project-name")
        self.description = page.get_by_test_id("project-description")
        self.create_button = page.get_by_test_id("project-create")
        self.error = page.get_by_test_id("project-error")
        self.empty_state = page.get_by_test_id("projects-empty")
        self.cards = page.get_by_test_id("project-card")
        self.current_user = page.get_by_test_id("current-user")
        self.logout = page.get_by_test_id("logout")

    def create(self, name: str, description: str = "") -> None:
        self.name.fill(name)
        self.description.fill(description)
        self.create_button.click()

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_test_id("project-link").filter(has_text=exact(name)))

    def open_project(self, name: str) -> ProjectPage:
        self.card(name).get_by_test_id("project-link").click()
        project_page = ProjectPage(self.page)
        expect(project_page.title).to_have_text(name)
        return project_page


class ProjectPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.title = page.get_by_test_id("project-title")
        self.task_title = page.get_by_test_id("task-title")
        self.task_priority = page.get_by_test_id("task-priority")
        self.task_due_date = page.get_by_test_id("task-due-date")
        self.add_button = page.get_by_test_id("task-add")
        self.error = page.get_by_test_id("task-error")
        self.rows = page.get_by_test_id("task-row")
        self.status_filter = page.get_by_test_id("status-filter")
        self.back = page.get_by_test_id("back-to-projects")

    def add_task(self, title: str, priority: str = "medium", due_date: str | None = None) -> Locator:
        self.task_title.fill(title)
        self.task_priority.select_option(priority)
        if due_date:
            self.task_due_date.fill(due_date)
        self.add_button.click()
        row = self.row(title)
        expect(row).to_be_visible()
        return row

    def row(self, title: str) -> Locator:
        return self.rows.filter(has=self.page.get_by_test_id("task-title-text").filter(has_text=exact(title)))

    def move(self, title: str, status: str) -> None:
        self.row(title).get_by_test_id(f"task-action-{status}").click()
        expect(self.row(title)).to_have_attribute("data-status", status)

    def delete(self, title: str) -> None:
        self.row(title).get_by_test_id("task-delete").click()
        expect(self.row(title)).to_have_count(0)

    def filter_by(self, status: str) -> None:
        self.status_filter.select_option(status)
