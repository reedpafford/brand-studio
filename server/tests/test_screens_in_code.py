"""Brand screens attached in code (the Director's findings on #556; Reed's CTA rule): the end
line's shot shows the brand's real screen on the hero's phone, and every screen a shot lists
is attached to its clip and its frame, so "screen isn't attached" never blocks. Free."""

import copy

from app import clip_prompts, storyboard
from app.models.brands import Brand, BrandScreen
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, ClipPrompts, Frame, Reference
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_project_clips import _prompt

UI_CLIP = ": keep its UI, logo and layout; the coin, numbers and chart are what the shot says."
UI_STILL = ": keep its UI, logo and layout; the coin, numbers and chart are what this frame says."


def _cast(editor, db, setup) -> tuple[Project, int]:  # noqa: F811
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    )
    with_sheet(db, mom.json()["id"])
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom.json()["id"]]})
    project = db.get(Project, setup["project"])
    db.get(Brand, project.brand_id).end_line = "I bought the dip."  # shot 1.2's line
    db.get(BrandScreen, setup["screen"]).balance = "$348,920"  # the balance screen
    db.commit()
    return project, mom.json()["id"]


def _bd(mom: int) -> dict:
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mom}"]  # the hero
    return bd


def test_the_end_lines_shot_shows_the_balance_screen_on_the_heros_phone(app, db, editor, setup):  # noqa: F811
    project, mom = _cast(editor, db, setup)
    db.get(Brand, project.brand_id).name = "Dip"  # the closing line names the brand (rules 18)
    db.commit()
    editor.post(f"/projects/{project.id}/breakdown")
    _run(app, db, FakeClaude(_bd(mom)))
    got = editor.get(f"/projects/{project.id}/breakdown").json()
    cta = got["breakdown"]["scenes"][0]["shots"][1]
    assert cta["screen_ids"] == [f"screen:{setup['screen']}"]
    assert cta["character_ids"] == [f"char:{mom}"]
    assert "Advice: Shot 1.2 now shows the Buy screen on Mom's phone." in got["problems"]


def test_a_clip_and_a_frame_attach_every_screen_their_shots_show(app, db, editor, setup):  # noqa: F811
    project, mom = _cast(editor, db, setup)
    screen = f"screen:{setup['screen']}"
    data = _bd(mom)
    data["scenes"][0]["shots"][1]["screen_ids"] = [screen]
    bd = Breakdown.model_validate(data)
    # The clip's AI left the screen out: it's attached in code, last, on the References line.
    prompt = _prompt().replace(' [Image2] is the fomo "Buy" screen.', "")
    mine = [Reference(kind="image", id=f"char:{mom}", role="Mom")]
    clip = ClipPrompt(clip_id="c1", seconds=5, prompt=prompt, references=mine)
    fixed = clip_prompts.with_cast(db, project, clip, bd)
    assert [r.id for r in fixed.references] == [f"char:{mom}", screen]
    assert "[Image2] is the Buy screen" + UI_CLIP in fixed.prompt
    found = check.clip_prompts(bd, ClipPrompts(clips=[fixed]), 9, 3)
    assert not [p for p in found if "isn't attached" in p]
    left = check.clip_prompts(bd, ClipPrompts(clips=[clip]), 9, 3)
    assert [p for p in left if "screen" in p and "attached" in p][0].startswith("Advice: ")
    # The frame of that shot gets it too.
    frame = Frame(clip_id="c1", shot_id="1.2", prompt="Nate holds up his phone.",
                  reference_ids=[f"char:{mom}"])  # fmt: skip
    drawn = storyboard.with_cast(db, project, frame, bd)
    assert drawn.reference_ids == [f"char:{mom}", screen]
    assert "Show the Buy screen from image 2" + UI_STILL in drawn.prompt
    assert storyboard.with_cast(db, project, drawn, bd) == drawn  # again changes nothing


def _trading(db, editor, owner, setup):  # noqa: F811
    """fomo with a logo, two trading screens and Home; shot 1.1 trades, 1.2 is the CTA."""
    project, mom = _cast(editor, db, setup)
    brand = db.get(Brand, project.brand_id)
    brand.logo_file_id = logo = upload(owner)
    db.commit()

    def screen(name: str, tags: list[str]) -> str:
        body = {"name": name, "file_id": upload(editor), "tags": tags}
        made = editor.post(f"/brands/{brand.id}/screens", json=body)
        return f"screen:{made.json()['id']}"

    up, down = screen("Token chart up", ["trading"]), screen("Token chart down", ["trading"])
    home = screen("Home", ["mobile", "home"])
    data = _bd(mom)
    data["scenes"][0]["shots"][0]["screen_ids"] = [up, down]  # a montage win and dip
    data["scenes"][0]["shots"][1]["screen_ids"] = [home]  # the CTA
    return project, f"char:{mom}", logo, (up, down, home), data


def test_a_trading_beat_attaches_its_real_screens_as_given(
    app,
    db,
    editor,
    owner,
    setup,  # noqa: F811
):
    """Reed, 30 Oct ("actual fomo UI always", rule 14 replaced): a trading screen is attached as
    it is, never swapped for the logo with an invented screen; the CTA keeps the real Home."""
    project, char, logo, (up, down, home), data = _trading(db, editor, owner, setup)
    mom = int(char[5:])
    bd = Breakdown.model_validate(data)
    known = clip_prompts.assets(db, project)
    assert logo not in known[up][2] + known[down][2]  # the screens' own pictures
    assert known[up][0].split(" | ")[1] == "screen"  # never "logo"
    mine = [Reference(kind="image", id=f"char:{mom}", role="Mom")]
    clip = ClipPrompt(clip_id="c1", seconds=5, prompt=_prompt(), references=mine)
    fixed = clip_prompts.with_cast(db, project, clip, bd)
    ids = [r.id for r in fixed.references]
    assert ids[0] == f"char:{mom}" and {up, down, home} <= set(ids)
    n = ids.index(up) + 1
    assert f"[Image{n}] is the Token chart up screen" + UI_CLIP in fixed.prompt
    assert "fomo logo" not in fixed.prompt  # never the logo in place of the screen
    assert not [p for p in clip_prompts.clip_problems(db, project, bd, fixed) if "attached" in p]
    assert clip_prompts.with_cast(db, project, fixed, bd) == fixed
    frame = Frame(clip_id="c1", shot_id="1.1", prompt="Mom checks her phone.",
                  reference_ids=[f"char:{mom}"])  # fmt: skip
    drawn = storyboard.with_cast(db, project, frame, bd)
    assert drawn.reference_ids == [f"char:{mom}", up, down]
    assert "Show the Token chart up screen from image 2" + UI_STILL in drawn.prompt
    assert "fomo logo" not in drawn.prompt
    cta = storyboard.with_cast(db, project, frame.model_copy(update={"shot_id": "1.2",
                               "reference_ids": [f"char:{mom}"]}), bd)  # fmt: skip
    assert cta.reference_ids == [f"char:{mom}", home]
    assert "Show the Home screen from image 2" + UI_STILL in cta.prompt
