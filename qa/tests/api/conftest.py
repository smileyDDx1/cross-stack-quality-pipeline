import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/api/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.api)
