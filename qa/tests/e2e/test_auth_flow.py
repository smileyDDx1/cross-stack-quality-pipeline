import re

from playwright.sync_api import Page, expect

from framework import factories
from framework.assertions import expect_status
from framework.schemas import Token, parse

from .pages import AuthPage, ProjectsPage


def test_new_user_can_register_and_lands_on_empty_dashboard(page: Page, api):
    payload = factories.user_payload()

    AuthPage(page).open().register(payload["email"], payload["password"], payload["displayName"])

    projects = ProjectsPage(page)
    expect(projects.current_user).to_have_text(payload["displayName"])
    expect(projects.empty_state).to_be_visible()

    # Registered through the UI, so remove the account through the API.
    token = parse(Token, expect_status(api.auth.login(payload["email"], payload["password"]), 200)).access_token
    expect_status(api.as_user(token).auth.delete_me(), 204)


def test_existing_user_can_sign_in_and_out(page: Page, account):
    auth = AuthPage(page).open()
    auth.sign_in(account.email, account.password)

    projects = ProjectsPage(page)
    expect(projects.current_user).to_have_text(account.user.display_name)

    projects.logout.click()
    expect(auth.submit).to_be_visible()
    expect(page).to_have_url(re.compile(r"#/login$"))
    expect(projects.current_user).to_be_hidden()


def test_wrong_password_shows_an_error_and_stays_signed_out(page: Page, account):
    auth = AuthPage(page).open()
    auth.sign_in(account.email, "Wrong-passw0rd")

    expect(auth.error).to_have_text("Invalid email or password.")
    expect(ProjectsPage(page).current_user).to_be_hidden()


def test_registration_errors_from_the_api_are_shown(page: Page):
    payload = factories.user_payload(password="short")

    AuthPage(page).open().register(payload["email"], payload["password"], payload["displayName"])

    expect(AuthPage(page).error).to_contain_text("Password must be")
