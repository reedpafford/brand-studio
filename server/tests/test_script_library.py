"""The Script Library: scripts, versions, approval, publishing and who sees what."""

from tests.helpers import assert_hidden, assert_no_dollars

SCRIPT = (
    "SCENE 1 — INT. KITCHEN — DAY\nMOM: Nate, where is all your money?\nNATE: I bought the dip."
)


def _make(client, **extra) -> dict:
    fomo = client.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "title": "Dip", "description": "Mom finds the wallet", **extra}
    r = client.post("/scripts", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_write_approve_and_publish_a_script(owner):
    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    url = f"/scripts/{made['id']}"
    (original,) = made["versions"]
    assert (original["slot"], original["status"], original["words"]) == (0, "draft", 19)
    assert original["seconds"] == 2 and made["status"] == "draft"  # 10 spoken words / 4.8
    variation = owner.put(f"{url}/drafts/1", json={"text": SCRIPT + "\nNATE: Fine."}).json()
    assert [v["slot"] for v in variation["versions"]] == [0, 1]
    assert owner.post(f"{url}/publish").status_code == 409  # versions not approved yet
    owner.post(f"{url}/drafts/0/approve")
    again = owner.put(f"{url}/drafts/0", json={"text": "changed"})
    assert again.status_code == 409 and "approved" in again.json()["detail"]
    assert owner.delete(f"{url}/drafts/0").status_code == 409  # the original stays
    owner.delete(f"{url}/drafts/1")
    published = owner.post(f"{url}/publish").json()
    assert (published["status"], published["versions_left"]) == ("published", 1)
    final = owner.patch(url, json={"title": "New"})
    assert final.status_code == 409 and "Duplicate" in final.json()["detail"]
    copy = owner.post(f"{url}/duplicate").json()
    assert copy["title"] == "Dip (copy)" and not copy["published"]
    assert copy["versions"][0]["status"] == "draft" and copy["versions"][0]["text"] == SCRIPT
    assert owner.post("/scripts", json={**_body(owner), "reference_id": "nope"}).status_code == 404


def _body(client) -> dict:
    return {"brand_id": client.get("/brands").json()[0]["id"], "title": "X"}


def test_editors_see_published_and_their_own_and_change_only_their_own(owner, editor):
    private = _make(owner, title="Owner draft", text=SCRIPT)
    public = _make(owner, title="Owner published", text=SCRIPT)
    owner.post(f"/scripts/{public['id']}/drafts/0/approve")
    owner.post(f"/scripts/{public['id']}/publish")
    mine = _make(editor, title="Editor's own")
    titles = {s["title"] for s in editor.get("/scripts").json()}
    assert titles == {"Owner published", "Editor's own"}
    assert editor.get(f"/scripts/{private['id']}").status_code == 404
    assert editor.put(f"/scripts/{public['id']}/drafts/0", json={"text": "x"}).status_code in (
        403,
        409,
    )
    assert editor.put(f"/scripts/{mine['id']}/drafts/0", json={"text": SCRIPT}).status_code == 200
    assert {s["title"] for s in owner.get("/scripts").json()} >= {"Owner draft", "Editor's own"}
    assert editor.delete(f"/scripts/{public['id']}").status_code == 403
    assert editor.delete(f"/scripts/{mine['id']}").status_code == 204
    assert_no_dollars(editor, ["/scripts", f"/scripts/{public['id']}"])


def test_library_filters_and_search(owner):
    a = _make(owner, title="Altar", text=SCRIPT, reference_id="fomo-DehudnaAmce")
    _make(
        owner, title="Bus", text="MAYA: Did you see STONK? It's flying, everyone's buying it now."
    )
    assert [s["title"] for s in owner.get("/scripts", params={"q": "stonk"}).json()] == ["Bus"]
    assert [s["title"] for s in owner.get("/scripts", params={"reference": True}).json()] == [
        "Altar"
    ]
    owner.post(f"/scripts/{a['id']}/drafts/0/approve")
    owner.post(f"/scripts/{a['id']}/publish")
    assert [s["title"] for s in owner.get("/scripts", params={"status": "published"}).json()] == [
        "Altar"
    ]
    left = owner.get("/scripts", params={"versions_left": 1}).json()
    assert [s["title"] for s in left] == ["Altar"]
    assert owner.get("/scripts", params={"min_seconds": 100}).json() == []


def test_other_workspace_cannot_see_scripts(owner, outsider):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}"
    assert_hidden(
        outsider,
        [("GET", url), ("PATCH", url, {"title": "x"}), ("DELETE", url), ("POST", f"{url}/publish")],
    )
    assert outsider.get("/scripts").json() == []


def test_bulk_create_is_all_or_none(owner):
    fomo = owner.get("/brands").json()[0]["id"]
    rows = [
        {"brand_id": fomo, "title": "Altar", "reference_id": "fomo-DehudnaAmce"},
        {"brand_id": fomo, "title": "Bus", "description": "School bus, STONK flying"},
    ]
    made = owner.post("/scripts/bulk", json={"scripts": rows})
    assert made.status_code == 201, made.text
    assert [s["title"] for s in made.json()] == ["Altar", "Bus"]
    assert all(s["versions"][0]["status"] == "draft" for s in made.json())  # nothing written yet
    bad = owner.post("/scripts/bulk", json={"scripts": [rows[1], {**rows[0], "brand_id": 999}]})
    assert bad.status_code == 404 and bad.json()["detail"].startswith("Row 2:")
    assert len(owner.get("/scripts").json()) == 2  # the bad batch added nothing


def test_undo_approval_and_earlier_texts_until_published(owner, editor):
    """#250: approve and undo per version, and a version's earlier texts to bring back."""
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}"
    owner.put(f"{url}/drafts/0", json={"text": SCRIPT + "\nMOM: Wow."})
    owner.put(f"{url}/drafts/0", json={"text": "MOM: Third try."})
    history = owner.get(f"{url}/drafts/0/history").json()
    assert [h["text"] for h in history] == [SCRIPT + "\nMOM: Wow.", SCRIPT]  # newest first
    assert history[0]["source"] == "edit" and history[0]["created_by_name"] == "Reed"
    owner.put(f"{url}/drafts/0", json={"text": history[1]["text"]})  # bring the first back
    assert owner.get(url).json()["versions"][0]["text"] == SCRIPT
    owner.post(f"{url}/drafts/0/approve")
    undone = owner.delete(f"{url}/drafts/0/approve").json()
    assert undone["versions"][0]["status"] == "draft"
    assert owner.put(f"{url}/drafts/0", json={"text": SCRIPT}).status_code == 200  # editable
    owner.put(f"{url}/drafts/1", json={"text": "NATE: A variation."})
    assert owner.delete(f"{url}/drafts/1").status_code == 200  # a variation can be removed
    owner.post(f"{url}/drafts/0/approve")
    owner.post(f"{url}/publish")
    final = owner.delete(f"{url}/drafts/0/approve")
    assert final.status_code == 409 and "Duplicate" in final.json()["detail"]
    assert editor.get(f"{url}/drafts/0/history").status_code == 403  # author and owner only
    assert editor.delete(f"{url}/drafts/0/approve").status_code in (403, 409)


def test_a_version_keeps_its_newest_20_earlier_texts(owner, editor):
    made = _make(owner, text="MOM: Take 0.")
    url = f"/scripts/{made['id']}"
    for n in range(1, 23):
        owner.put(f"{url}/drafts/0", json={"text": f"MOM: Take {n}."})
    history = owner.get(f"{url}/drafts/0/history").json()
    assert len(history) == 20
    assert (history[0]["text"], history[-1]["text"]) == ("MOM: Take 21.", "MOM: Take 2.")
    mine = _make(editor, text="NATE: One.")
    editor.put(f"/scripts/{mine['id']}/drafts/0", json={"text": "NATE: Two."})
    assert len(editor.get(f"/scripts/{mine['id']}/drafts/0/history").json()) == 1  # the author
