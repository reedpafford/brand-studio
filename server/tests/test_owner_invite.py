import pytest

from app.models.accounts import Role, User
from app.owner_invite import invite_first_owner
from tests.conftest import PASSWORD


def test_the_first_owner_joins_by_invite_and_only_the_newest_link_works(app, client, db):
    state = app.state
    first = invite_first_owner(db, state.storage, state.settings, "reed@example.com")
    newest = invite_first_owner(db, state.storage, state.settings, "reed@example.com")
    assert client.post("/auth/invite", json={"token": first}).status_code == 404
    assert client.post("/auth/invite", json={"token": newest}).json()["role"] == "owner"
    r = client.post(
        "/auth/accept-invite", json={"token": newest, "name": "Reed", "password": PASSWORD}
    )
    assert r.status_code == 201 and r.json()["role"] == Role.owner
    assert client.get("/auth/me").json()["email"] == "reed@example.com"
    assert client.post("/auth/setup", json={}).status_code in (403, 409, 422)
    with pytest.raises(SystemExit, match="already has an owner"):
        invite_first_owner(db, state.storage, state.settings, "someone@example.com")
    assert db.query(User).count() == 1


def test_the_test_site_signs_in_with_its_own_cookie(app, client, db):
    """Live and the test site share an address (cookies ignore ports): never each other's."""
    app.state.settings.cookie_name = "bs_next_session"
    raw = invite_first_owner(db, app.state.storage, app.state.settings, "reed@example.com")
    client.post("/auth/accept-invite", json={"token": raw, "name": "Reed", "password": PASSWORD})
    assert list(client.cookies.keys()) == ["bs_next_session"]
    assert client.get("/auth/me").status_code == 200
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
