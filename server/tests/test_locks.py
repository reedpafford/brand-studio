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
                                                "song": False, "screens": [], "roles": []},
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


def test_every_clip_keeps_the_videos_outfit_in_its_own_words(owner, editor, db):
    """284: the Keep line said "this video's champagne satin dress" and each clip drew a new
    neckline. Each person's outfit as set, with its cut and fabric, is in every clip's Keep
    line once (free): kept when a clause names them with it (the article dropped or not), an
    older one of theirs replaced, never in a clip whose shots change their clothes."""
    from app.clip_prompts import _pictures, _worn
    from app.clip_prompts import assets as clip_assets

    pid, mia, kid = _video(owner, editor, db)
    worn = "a sleeveless champagne satin sheath, high round neck"
    editor.put(f"/projects/{pid}/locks",
               json={"outfits": {f"char:{kid}": worn, f"char:{mia}": worn}})  # fmt: skip
    project = db.get(Project, pid)
    db.refresh(project)
    known = clip_assets(db, project)
    pics, both = _pictures(known), [f"char:{kid}", f"char:{mia}"]
    bare = worn.removeprefix("a ")

    def keep(text: str, said: str = "", who=both) -> str:
        return _worn(f"Audio: x.\nShot 1 | 0-3 s. They wait.\nKeep: {text}\nAudio: x.", who,
                     known, pics, said).splitlines()[2]  # fmt: skip

    added = keep("Kid as in [Image2], the same look as on their sheet.", who=[f"char:{kid}"])
    assert added.endswith(f"Kid in this video's {bare}.") and "'s a " not in added
    assert keep(added.removeprefix("Keep: "), who=[f"char:{kid}"]) == added  # again: the same
    said = f"Kid as in [Image2], in this video's {bare}."  # the writer's own words, kept
    assert keep(said, who=[f"char:{kid}"]) == f"Keep: {said}"
    assert keep(said).endswith(f"Mia in this video's {bare}.")  # each person, by name
    older = keep("Kid as in [Image2], in this video's green dress.", who=[f"char:{kid}"])
    assert older == f"Keep: Kid as in [Image2], in this video's {bare}."  # replaced, not twice
    pinned = (
        "Kid as in [Image2], in the champagne satin dress; Mia as in [Image3], in this "
        "video's long red wool coat, never in Kid's satin dress."
    )  # QA: Mia's names Kid
    once = keep(pinned, who=[f"char:{kid}"])
    assert "never in Kid's satin dress." in once and once.endswith(f"Kid in this video's {bare}.")
    assert keep(once.removeprefix("Keep: "), who=[f"char:{kid}"]) == once  # one run settles it
    assert keep("Kid as in [Image2], in this video's green dress, never Mia's red coat.") == (
        f"Keep: Kid as in [Image2], in this video's {bare}, never Mia's red coat. "
        f"Mia in this video's {bare}."
    )  # only the outfit words go; the never-pin stays
    assert keep("Kid as in [Image2].", "Kid puts on a smile; the plane takes off.",
                [f"char:{kid}"]).endswith(bare + ".")  # not a change of clothes  # fmt: skip
    assert keep("Kid as in [Image2].", "Kid changes into pyjamas.", [f"char:{kid}"]) == (
        "Keep: Kid as in [Image2]."
    )  # the script changes it here
