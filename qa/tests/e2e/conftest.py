import json

import pytest
from playwright.sync_api import Page, expect

from framework.steps import Account

TOKEN_KEY = "tasktracker.token"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/e2e/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, settings):
    return {**browser_context_args, "base_url": settings.base_url}


@pytest.fixture(autouse=True)
def _default_timeouts(page: Page) -> None:
    page.set_default_timeout(10_000)
    expect.set_options(timeout=10_000)


@pytest.fixture
def signed_in_page(page: Page, account: Account) -> Page:
    """A page that starts already signed in, by seeding the token the app keeps in sessionStorage.

    Only the login tests drive the login form. Everything else skips it, which keeps those tests fast
    and stops one broken login screen from failing the whole UI suite.
    """
    page.add_init_script(f"window.sessionStorage.setItem({json.dumps(TOKEN_KEY)}, {json.dumps(account.token)})")
    page.goto("/")
    expect(page.get_by_test_id("current-user")).to_have_text(account.user.display_name)
    return page
