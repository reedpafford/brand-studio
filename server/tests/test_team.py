from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_editor_joins_with_editor_role(editor):
    assert editor.get("/auth/me").json()["role"] == "editor"


def test_members_listed_for_everyone(editor):
    names = [m["name"] for m in editor.get("/team/members").json()]
    assert names == ["Reed", "Ed"]


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
