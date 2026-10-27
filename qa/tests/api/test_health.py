from framework.assertions import expect_status


def test_health_reports_database_up(api):
    body = expect_status(api.session.get("/health"), 200).json()
    assert body == {"status": "healthy", "database": "up"}


def test_unknown_route_returns_problem_details(api):
    response = expect_status(api.session.get("/api/does-not-exist"), 404)
    assert response.headers["Content-Type"].startswith("application/problem+json")
