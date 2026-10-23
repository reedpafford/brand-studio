from fastapi.testclient import TestClient

from app.models.accounts import User
from tests.conftest import PASSWORD, SETUP_TOKEN

SETUP = {
    "workspace_name": "S",
    "email": "x@example.com",
    "name": "X",
    "password": PASSWORD,
}


def test_setup_needs_the_server_token(client):
    r = client.post("/auth/setup", json={**SETUP, "setup_token": "wrong"})
    assert r.status_code == 403


def test_setup_only_works_once(owner):
    r = owner.post("/auth/setup", json={**SETUP, "setup_token": SETUP_TOKEN})
    assert r.status_code == 409


def test_login_logout_round_trip(owner):
    owner.post("/auth/logout")
    assert owner.get("/auth/me").status_code == 401
    r = owner.post("/auth/login", json={"email": "REED@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert owner.get("/auth/me").json()["role"] == "owner"


def test_wrong_password_and_unknown_email_look_the_same(owner):
    bad = owner.post("/auth/login", json={"email": "reed@example.com", "password": "nope"})
    unknown = owner.post("/auth/login", json={"email": "who@example.com", "password": "nope"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()


def test_session_cookie_is_http_only(client):
    r = client.post("/auth/setup", json={**SETUP, "setup_token": SETUP_TOKEN})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_password_is_not_stored_in_plain_text(owner, db):
    assert PASSWORD not in db.query(User).one().password_hash


def test_invite_token_works_once(app, owner):
    token = owner.post("/team/invites", json={"email": "a@example.com"}).json()["token"]
    body = {"token": token, "name": "A", "password": PASSWORD}
    with TestClient(app) as c:
        assert c.post("/auth/accept-invite", json=body).status_code == 201
        assert c.post("/auth/accept-invite", json=body).status_code == 400
