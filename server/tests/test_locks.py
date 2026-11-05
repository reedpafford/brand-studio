"""A video's locks and its own outfits (director-chat.md §1; FOMO-Producer: Kimchi's mustard
trench coat was overridden by the sheet). Free: no paid calls."""

from fastapi.testclient import TestClient

from app.enhance import project_context
from app.models.projects import Project
from app.storyboard import assets
from tests.conftest import PASSWORD
from tests.helpers import with_sheet
from tests.test_cast_roles import _video


def test_locks_and_outfits_are_set_by_whoever_may_change_the_video(app, owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    url = f"/projects/{pid}/locks"
    assert editor.get(url).json() == {"locks": {"cast": False, "look": False, "length": False,
                                                "song": False, "screens": []},
                                      "outfits": {}}  # fmt: skip
    body = {"locks": {"cast": True, "screens": [3]},
            "outfits": {f"char:{kid}": "  mustard trench coat, black boots "}}  # fmt: skip
    saved = editor.put(url, json=body).json()
    assert saved["locks"]["cast"] and saved["locks"]["screens"] == [3]
    assert saved["outfits"] == {f"char:{kid}": "mustard trench coat, black boots"}
    project = db.get(Project, pid)
    db.refresh(project)
    assert project.locks == {"cast": True, "screens": [3]}  # only what's locked is kept

    stranger = editor.put(url, json={"outfits": {"char:9999": "a hat"}})
    assert stranger.status_code == 422 and "char:9999" in stranger.json()["detail"]
    cleared = editor.put(url, json={"outfits": {f"char:{kid}": ""}}).json()  # unlocked too
    assert cleared["outfits"] == {} and not cleared["locks"]["cast"]

    token = owner.post("/team/invites", json={"email": "bo@example.com"}).json()["token"]
    with TestClient(app) as other:  # another editor reads the video but can't change it
        other.post("/auth/accept-invite", json={"token": token, "name": "Bo", "password": PASSWORD})
        assert other.get(url).status_code == 200
        assert other.put(url, json=body).status_code == 403
    assert owner.put(url, json=body).status_code == 200


def test_the_videos_outfit_is_in_every_cast_line_and_the_stills_asset_line(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    editor.put(f"/projects/{pid}/locks",
               json={"outfits": {f"char:{kid}": "mustard trench coat"}})  # fmt: skip
    project = db.get(Project, pid)
    db.refresh(project)
    _, message = project_context(db, project, "breakdown")
    cast = message.split("<cast>")[1]
    kids = next(line for line in cast.splitlines() if line.startswith(f"char:{kid} |"))
    assert kids.endswith("| wears: mustard trench coat (this video)")
    mias = next(line for line in cast.splitlines() if line.startswith(f"char:{mia} |"))
    assert "wears:" not in mias  # no outfit given: the sheet's, as before
    line, _ = assets(db, project)[f"char:{kid}"]
    assert line.endswith("wears: mustard trench coat (this video)")


def test_with_an_outfit_the_sheet_line_never_says_not_to_describe_clothes(owner, editor, db):
    """QA on #1104: "never describe … coat" then "wears: a raincoat" was a mixed message."""
    pid, _, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    project = db.get(Project, pid)
    plain, _ = assets(db, project)[f"char:{kid}"]
    assert "never describe their face, breed, coat, skin" in plain  # no outfit: as before
    editor.put(f"/projects/{pid}/locks", json={"outfits": {f"char:{kid}": "a yellow raincoat"}})
    db.refresh(project)
    line, _ = assets(db, project)[f"char:{kid}"]
    assert "coat," not in line and "except for what they wear" in line
    assert line.endswith("wears: a yellow raincoat (this video)")
