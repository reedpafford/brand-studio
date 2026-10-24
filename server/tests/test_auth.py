from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.accounts import Invite, LoginSession, User
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
        info = c.post("/auth/invite", json={"token": token})  # no login needed
        assert info.json() == {
            "workspace_name": "Studio",
            "invited_by_name": "Reed",
            "email": "a@example.com",
            "role": "editor",
        }
        assert c.post("/auth/accept-invite", json=body).status_code == 201
        assert c.post("/auth/accept-invite", json=body).status_code == 400
        used = c.post("/auth/invite", json={"token": token})
        assert used.status_code == 404
        assert used.json()["detail"] == "This invite link is not valid any more."
        assert c.post("/auth/invite", json={"token": "made-up"}).status_code == 404


def _login(client, password):
    return client.post("/auth/login", json={"email": "reed@example.com", "password": password})


def test_login_locks_after_repeated_failures(owner):
    for _ in range(5):
        assert _login(owner, "wrong").status_code == 401
    assert _login(owner, "wrong").status_code == 429
    assert _login(owner, PASSWORD).status_code == 429  # locked even with the right password


def test_success_resets_the_email_counter(owner):
    for _ in range(4):
        _login(owner, "wrong")
    assert _login(owner, PASSWORD).status_code == 200
    assert _login(owner, "wrong").status_code == 401


def test_setup_token_guessing_is_throttled(app, client):
    app.state.settings.login_max_failures_per_ip = 2
    for _ in range(2):
        assert client.post("/auth/setup", json={**SETUP, "setup_token": "x"}).status_code == 403
    r = client.post("/auth/setup", json={**SETUP, "setup_token": SETUP_TOKEN})
    assert r.status_code == 429


def test_setup_race_loser_gets_409(owner, monkeypatch):
    # Pretend the "already set up?" check ran before the other request committed.
    monkeypatch.setattr(Session, "get", lambda *a, **k: None)
    r = owner.post("/auth/setup", json={**SETUP, "setup_token": SETUP_TOKEN})
    assert r.status_code == 409


def test_expired_session_is_refused(owner, db):
    db.execute(update(LoginSession).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    assert owner.get("/auth/me").status_code == 401


def test_expired_invite_is_refused(app, owner, db):
    token = owner.post("/team/invites", json={"email": "a@example.com"}).json()["token"]
    db.execute(update(Invite).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    with TestClient(app) as c:
        r = c.post("/auth/accept-invite", json={"token": token, "name": "A", "password": PASSWORD})
        assert r.status_code == 400
        assert c.post("/auth/invite", json={"token": token}).status_code == 404
