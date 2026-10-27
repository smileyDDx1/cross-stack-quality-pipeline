from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from framework.clients import ApiClient
from framework.config import Settings
from framework.session import ApiSession, traffic, wait_until_healthy
from framework.steps import Account, register_and_login


@pytest.fixture(scope="session")
def settings() -> Settings:
    settings = Settings.from_env()
    wait_until_healthy(settings)
    return settings


@pytest.fixture
def api(settings: Settings) -> ApiClient:
    """Anonymous client."""
    return ApiClient(ApiSession(settings))


@pytest.fixture
def account_factory(api: ApiClient) -> Iterator[Callable[..., Account]]:
    """Creates throwaway accounts and deletes them (and, by cascade, all their data) after the test.

    Every test works inside its own accounts, which is what keeps parallel workers and parallel CI runs
    from seeing each other's data, even though they share one database.
    """
    created: list[Account] = []

    def make(**overrides) -> Account:
        account = register_and_login(api, **overrides)
        created.append(account)
        return account

    yield make

    for account in created:
        response = api.as_user(account.token).auth.delete_me()
        assert response.status_code in (204, 401), f"Cleanup failed for {account.email}: {response.status_code}"


@pytest.fixture
def account(account_factory: Callable[..., Account]) -> Account:
    return account_factory()


@pytest.fixture
def client(api: ApiClient, account: Account) -> ApiClient:
    """Client authenticated as this test's own account."""
    return api.as_user(account.token)


@pytest.fixture
def other_client(api: ApiClient, account_factory: Callable[..., Account]) -> ApiClient:
    """Client for a second, unrelated account (for authorization tests)."""
    return api.as_user(account_factory().token)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    traffic.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.failed and report.when in ("setup", "call"):
        log = traffic.dump()
        if log:
            report.sections.append(("HTTP traffic (oldest first)", log))
