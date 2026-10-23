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
