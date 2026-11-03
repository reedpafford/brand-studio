from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_editor_joins_with_editor_role(editor):
    assert editor.get("/auth/me").json()["role"] == "editor"


def test_members_listed_for_everyone(owner, editor):
    for viewer in (editor, owner):  # names show plainly to everyone (Reed, 2026-10-28)
        assert [m["name"] for m in viewer.get("/team/members").json()] == ["Reed", "Ed"]
    emails = {v: [m["email"] for m in v.get("/team/members").json()] for v in (editor, owner)}
    assert emails[editor] == ["", "ed@example.com"]  # the owner's email stays the owner's
    assert emails[owner] == ["reed@example.com", "ed@example.com"]


def test_editor_cannot_invite_or_remove(editor):
    assert editor.post("/team/invites", json={"email": "z@example.com"}).status_code == 403
    assert editor.delete("/team/members/1").status_code == 403


def test_owner_can_cancel_invite(owner):
    invite = owner.post("/team/invites", json={"email": "z@example.com", "role": "owner"}).json()
    assert [i["email"] for i in owner.get("/team/invites").json()] == ["z@example.com"]
    assert owner.delete(f"/team/invites/{invite['id']}").status_code == 204
    assert owner.get("/team/invites").json() == []


def test_removed_member_is_logged_out_and_cannot_log_in(owner, editor):
    ed_id = editor.get("/auth/me").json()["id"]
    assert owner.delete(f"/team/members/{ed_id}").status_code == 204
    assert editor.get("/auth/me").status_code == 401
    r = editor.post("/auth/login", json={"email": "ed@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_owner_cannot_remove_self(owner):
    me = owner.get("/auth/me").json()["id"]
    assert owner.delete(f"/team/members/{me}").status_code == 400


def test_removed_member_can_be_invited_back(app, owner, editor):
    ed_id = editor.get("/auth/me").json()["id"]
    owner.delete(f"/team/members/{ed_id}")
    invite = owner.post("/team/invites", json={"email": "ed@example.com", "role": "owner"})
    assert invite.status_code == 201
    body = {"token": invite.json()["token"], "name": "Ed 2", "password": "a new password"}
    me = editor.post("/auth/accept-invite", json=body).json()
    assert (me["id"], me["name"], me["role"]) == (ed_id, "Ed 2", "owner")


def test_other_workspace_owner_cannot_see_or_cancel_invites(owner, outsider):
    invite = owner.post("/team/invites", json={"email": "z@example.com"}).json()
    assert outsider.get("/team/invites").json() == []
    assert outsider.delete(f"/team/invites/{invite['id']}").status_code == 404


def test_owner_gets_a_fresh_link_for_a_waiting_invite(app, owner, editor):
    old = owner.post("/team/invites", json={"email": "z@example.com"}).json()
    fresh = owner.post(f"/team/invites/{old['id']}/link")
    assert fresh.status_code == 200 and fresh.json()["token"] != old["token"]
    assert editor.post(f"/team/invites/{old['id']}/link").status_code == 403
    with TestClient(app) as c:
        body = {"name": "Zed", "password": PASSWORD}
        assert (
            c.post("/auth/accept-invite", json={**body, "token": old["token"]}).status_code >= 400
        )
        joined = c.post("/auth/accept-invite", json={**body, "token": fresh.json()["token"]})
        assert joined.status_code == 201
    assert owner.post(f"/team/invites/{old['id']}/link").status_code == 404  # accepted


def test_owner_changes_a_role_but_never_their_own(owner, editor, outsider):
    ed_id = editor.get("/auth/me").json()["id"]
    me = owner.get("/auth/me").json()["id"]
    assert editor.patch(f"/team/members/{ed_id}", json={"role": "owner"}).status_code == 403
    made = owner.patch(f"/team/members/{ed_id}", json={"role": "owner"})
    assert made.json()["role"] == "owner" and editor.get("/auth/me").json()["role"] == "owner"
    assert owner.patch(f"/team/members/{ed_id}", json={"role": "editor"}).json()["role"] == "editor"
    mine = owner.patch(f"/team/members/{me}", json={"role": "editor"})  # always one owner
    assert mine.status_code == 400 and mine.json()["detail"] == "You can't change your own role."
    assert outsider.patch(f"/team/members/{ed_id}", json={"role": "owner"}).status_code == 404


def test_a_removed_member_is_listed_and_brought_back(owner, editor):
    ed_id = editor.get("/auth/me").json()["id"]
    owner.delete(f"/team/members/{ed_id}")
    assert editor.get("/team/members?removed=true").status_code == 401  # signed out
    assert [m["name"] for m in owner.get("/team/members?removed=true").json()] == ["Ed"]
    back = owner.post(f"/team/members/{ed_id}/restore")
    assert (back.status_code, back.json()["role"]) == (200, "editor")  # Undo, same role
    r = editor.post("/auth/login", json={"email": "ed@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert [m["name"] for m in owner.get("/team/members").json()] == ["Reed", "Ed"]
    assert owner.post(f"/team/members/{ed_id}/restore").status_code == 404  # not removed
    assert editor.get("/team/members?removed=true").status_code == 403


def test_each_member_shows_when_they_were_last_active(owner, editor, db):
    from datetime import timedelta

    from app.auth import ACTIVE
    from app.db import utcnow
    from app.models.accounts import User

    ed = db.query(User).filter_by(email="ed@example.com").one()
    ed.last_active_at = None
    db.commit()
    rows = {m["name"]: m["last_active_at"] for m in owner.get("/team/members").json()}
    assert rows["Reed"] and rows["Ed"] is None  # the owner just asked; Ed hasn't since
    editor.get("/auth/me")
    db.expire_all()
    first = db.get(User, ed.id).last_active_at
    assert first and utcnow() - first < ACTIVE
    editor.get("/auth/me")  # within a few minutes: no new write
    db.expire_all()
    assert db.get(User, ed.id).last_active_at == first
    ed = db.get(User, ed.id)
    ed.last_active_at = stale = utcnow() - ACTIVE - timedelta(minutes=1)
    db.commit()
    editor.get("/auth/me")  # a few minutes on: kept again
    db.expire_all()
    assert db.get(User, ed.id).last_active_at > stale + ACTIVE


def test_the_standing_editor_link_works_once_and_can_be_revoked(app, owner, editor, outsider):
    assert owner.get("/team/invite-link").json() is None
    assert editor.post("/team/invite-link").status_code == 403
    first = owner.post("/team/invite-link")
    assert first.status_code == 201
    link = owner.post("/team/invite-link").json()  # a new one: the first stops working
    assert owner.get("/team/invite-link").json() == {"expires_at": link["expires_at"]}
    assert outsider.get("/team/invite-link").json() is None
    assert owner.get("/team/invites").json() == []  # never in the email invites
    with TestClient(app) as c:
        seen = c.post("/auth/invite", json={"token": link["token"]}).json()
        assert (seen["email"], seen["role"]) == ("", "editor")
        body = {"name": "Lee", "password": PASSWORD}
        old = c.post("/auth/accept-invite", json={**body, "token": first.json()["token"],
                                                   "email": "lee@example.com"})  # fmt: skip
        assert old.status_code == 400
        no_email = c.post("/auth/accept-invite", json={**body, "token": link["token"]})
        assert no_email.status_code == 422
        taken = {**body, "token": link["token"], "email": "ed@example.com"}
        assert c.post("/auth/accept-invite", json=taken).status_code == 409
        joined = c.post("/auth/accept-invite", json={**taken, "email": "lee@example.com"})
        assert joined.status_code == 201 and joined.json()["role"] == "editor"
    with TestClient(app) as c:  # works once
        again = {**body, "token": link["token"], "email": "kim@example.com"}
        assert c.post("/auth/accept-invite", json=again).status_code == 400
    assert owner.get("/team/invite-link").json() is None
    revoked = owner.post("/team/invite-link").json()
    assert owner.delete("/team/invite-link").status_code == 204
    assert owner.get("/team/invite-link").json() is None
    with TestClient(app) as c:
        gone = {**body, "token": revoked["token"], "email": "kim@example.com"}
        assert c.post("/auth/accept-invite", json=gone).status_code == 400
