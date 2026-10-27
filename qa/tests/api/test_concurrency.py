from concurrent.futures import ThreadPoolExecutor

from framework import factories
from framework.schemas import Page, Project, parse


def test_concurrent_duplicate_creates_yield_one_winner_and_no_500s(client):
    # The API checks for duplicates before inserting, so racing requests can all pass that check.
    # The unique index must turn the losers into 409s rather than unhandled 500s.
    payload = factories.project_payload()
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = sorted(pool.map(lambda _: client.projects.create(payload).status_code, range(8)))

    assert statuses.count(201) == 1, statuses
    assert set(statuses) <= {201, 409}, statuses
    assert parse(Page[Project], client.projects.list()).total == 1
