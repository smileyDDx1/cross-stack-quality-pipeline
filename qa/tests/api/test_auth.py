import pytest

from framework import factories
from framework.assertions import expect_problem, expect_status
from framework.schemas import Token, User, parse


def test_register_returns_created_user(api):
    payload = factories.user_payload()
    response = expect_status(api.auth.register(payload), 201)

    user = parse(User, response)
    assert user.email == payload["email"]
    assert user.display_name == payload["displayName"]
    assert response.headers["Location"].endswith("/api/auth/me")
    assert "password" not in response.text.lower()

    # Registered outside account_factory, so clean up here.
    token = parse(Token, api.auth.login(payload["email"], payload["password"])).access_token
    api.as_user(token).auth.delete_me()


def test_email_is_normalised_and_unique_case_insensitively(api, account_factory):
    account = account_factory(email=factories.unique("Mixed.Case").upper() + "@Example.TEST")
    assert account.user.email == account.user.email.lower()

    duplicate = factories.user_payload(email=account.email.upper())
    expect_problem(api.auth.register(duplicate), 409)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"email": ""}, "email"),
        ({"email": "not-an-email"}, "email"),
        ({"password": "short1"}, "password"),
        ({"password": "no-digits-here"}, "password"),
        ({"displayName": "   "}, "displayName"),
        ({"displayName": "x" * 101}, "displayName"),
    ],
    ids=["missing-email", "bad-email", "short-password", "password-without-digit", "blank-name", "long-name"],
)
def test_invalid_registration_is_rejected_with_field_errors(api, overrides, field):
    expect_problem(api.auth.register(factories.user_payload(**overrides)), 400, field=field)


def test_login_issues_a_token_that_authenticates(api, account):
    response = expect_status(api.auth.login(account.email, account.password), 200)
    token = parse(Token, response)
    assert token.token_type == "Bearer"
    assert token.expires_in > 0

    me = parse(User, expect_status(api.as_user(token.access_token).auth.me(), 200))
    assert me.id == account.user.id


def test_wrong_password_and_unknown_email_look_identical(api, account):
    wrong_password = expect_problem(api.auth.login(account.email, "Wrong-passw0rd"), 401)
    unknown_email = expect_problem(api.auth.login(factories.user_payload()["email"], account.password), 401)
    assert wrong_password.title == unknown_email.title


@pytest.mark.parametrize(
    "token",
    [None, "not-a-jwt", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.invalid-signature"],
    ids=["no-token", "garbage", "bad-signature"],
)
def test_protected_endpoints_require_a_valid_token(api, token):
    expect_status(api.as_user(token).projects.list(), 401)


def test_tampered_token_is_rejected(api, account):
    header, payload, signature = account.token.split(".")
    tampered = ".".join([header, payload, signature[::-1]])
    expect_status(api.as_user(tampered).auth.me(), 401)


def test_deleting_the_account_revokes_access(api, account):
    client = api.as_user(account.token)
    expect_status(client.auth.delete_me(), 204)

    expect_status(client.auth.me(), 401)
    expect_problem(api.auth.login(account.email, account.password), 401)
