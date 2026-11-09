"""Video 315: Marcus, alone in his car, says "Danny" three times, and Danny is never on screen.
The director's plan kept Marcus alone in every talker shot, yet Danny was made a role, drawn,
and attached to clips 1, 4 and 5, because the shots' words named him. A shot's cast list is
who it shows (Reed, 9 Nov: trust the plan): a clip gets a person's sheet only when its shots
list them. No paid calls: the stand-ins only."""

import json

from app import breakdown, clip_prompts
from app.cast_roles import all_slots
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.prompts.schemas import Breakdown
from tests.helpers import approve_cast
from tests.test_cast_gate import _drawn
from tests.test_script_library import _make

LINES = [
    "I owe my brother-in-law a public apology.",
    "Every Thanksgiving I laughed at him for staring at his phone at the table.",
    "Called him the crypto guy. In front of everybody.",
    "This year he finally showed me. Small trades on fomo, ten minutes a day.",
    "Then he showed me the balance.",
    "I didn't say a word for the rest of dinner.",
    "I downloaded it in the parking lot.",
    "Danny, you were right. Link's in my bio.",
]
SCRIPT = "\n".join(f"MARCUS: {line}" for line in LINES)
TALKER = [  # 315's plan, word for word where Danny is named: Marcus alone in his car
    ("1.1", "c1", [1], "Marcus, phone at arm's length in the driver's seat, drags a hand "
                       "down his face."),
    ("1.2", "c1", [2], "Marcus does a cruel impression of Danny, shoulders hunched, eyes "
                       "glued to an invisible phone in his free hand, then snaps back."),
    ("2.1", "c2", [3, 4], "Marcus throws up sarcastic air quotes, then holds up ten fingers."),
    ("3.1", "c3", [5, 6], "Marcus goes dead still, then presses his lips shut and nods."),
    ("4.1", "c4", [7], "Marcus bends over his phone exactly like the Danny he mocked, the "
                       "FOMO Home screen open in his hand."),
    ("5.1", "c5", [8], "Marcus lets out a defeated laugh with his palm up on 'Danny, you were "
                       "right', then points down on 'Link's in my bio'."),
]  # fmt: skip
BROLL = [  # 293's: the plan puts Danny on screen at the Thanksgiving table, in two clips
    ("2.2", "c2", "At the table, quiet Danny in a grey sweater hunches over his phone."),
    ("3.2", "c3", "Danny sets his phone face-down next to his plate, his ears going red."),
]
HANDS = "Danny leans in the window and hands him the phone, the FOMO Home screen open."
AUDIO = "Audio: only the spoken lines and the quiet inside of a parked car. No subtitles."


def _shot(sid, lines, action, who):
    line = " ".join(LINES[n - 1] for n in lines) if lines else None
    return {"id": sid, "script_lines": lines, "speaker": "Marcus" if lines else None,
            "line": line, "action": action, "reaction": None, "camera": "Selfie close-up",
            "seconds": 3, "character_ids": who, "place_id": None, "moment": None,
            "screen_ids": []}  # fmt: skip


def _video(owner, editor, broll=False, hands=False, inserts=False, part=False):
    """315's video from a published script: its id and Marcus's role. `broll`: 293's B-roll
    of Danny; `hands`: in shot 4.1 Danny hands him the phone, and the plan lists him there;
    `inserts`: two phone inserts that list nobody, "a text from Danny", in clips 2 and 3;
    `part`: an insert in clip 4 of Danny's hand, listing nobody (a plan from before it was
    asked to list someone seen only in part)."""
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    marcus = owner.post(f"{base}/cast", json={"role": "Marcus"}).json()[-1]["id"]
    shots = [(sid, clip, _shot(sid, lines, action, [f"slot:{marcus}"]))
             for sid, clip, lines, action in TALKER]  # fmt: skip
    shots += [(sid, clip, _shot(sid, [], action, ["person:Danny"]))
              for sid, clip, action in BROLL if broll]  # fmt: skip
    shots += [(sid, clip, _shot(sid, [], "Insert: the phone shows a text from Danny.", []))
              for sid, clip in (("2.2", "c2"), ("3.2", "c3")) if inserts]  # fmt: skip
    hand = "Danny's hand slides his phone across the table, the FOMO balance on it."
    shots += [("4.2", "c4", _shot("4.2", [], hand, []))] if part else []
    if hands:
        shots[4][2].update(action=HANDS, character_ids=[f"slot:{marcus}", "person:Danny"])
    shots.sort()
    bd = {"hook": "Marcus owes his brother-in-law an apology.",
          "scenes": [{"id": 1, "heading": "INT. MARCUS'S PARKED CAR - DAY", "look": "Overcast.",
                      "shots": [s for _, _, s in shots]}],
          "clips": [{"id": c, "shot_ids": [s for s, k, _ in shots if k == c], "seconds": 8,
                     "seam": "Cut."} for c in ("c1", "c2", "c3", "c4", "c5")]}  # fmt: skip
    assert owner.put(f"{base}/drafts/0/breakdown", json=bd).status_code == 200
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"], marcus


def _plan(db, pid) -> tuple[BreakdownVersion, dict[str, list[str]]]:
    """The newest plan and who each shot shows."""
    db.expire_all()
    row = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id)
    row = row.all()[-1]
    return row, {s["id"]: s["character_ids"] for s in row.data["scenes"][0]["shots"]}


def _cast(editor, db, pid) -> dict[str, tuple[str, int]]:
    """Every role's look made and drawn, the cast approved: {name: (its ref, its sheet)}."""
    for row in editor.get(f"/projects/{pid}/assets").json():
        if row["slot_id"] and not row["library_item_id"]:
            editor.post(f"/projects/{pid}/assets/slots/{row['slot_id']}/make-look")
    rows = editor.get(f"/projects/{pid}/assets").json()
    for row in rows:
        _drawn(db, editor, row["library_item_id"])
    approve_cast(editor, pid)
    return {r["role"]: (f"char:{r['library_item_id']}",
                        db.get(LibraryItem, r["library_item_id"]).sheet_file_id)
            for r in rows}  # fmt: skip


def _write(db, pid, cast, clip: str, names: list[str]) -> ProjectClip:
    """`clip`'s prompt as the writer answered it, with `names` attached (315's clip 1:
    Marcus and Danny), saved as the worker saves it."""
    project, (bd, _) = db.get(Project, pid), _plan(db, pid)
    said = [(sid, LINES[lines[0] - 1]) for sid, c, lines, _ in TALKER if c == clip]
    prompt = "\n".join([
        AUDIO,
        "References: " + " ".join(f"[Image{i}] is {n}." for i, n in enumerate(names, 1)),
        "Summary: In his parked car, Marcus confesses he owes his brother-in-law an apology.",
        *(f'Shot {i} | {(i - 1) * 8 // len(said)}-{i * 8 // len(said)} s. Selfie close-up. '
          f'Marcus: "{line}" Only Marcus speaks.' for i, (_, line) in enumerate(said, 1)),
        "Keep: one Marcus, the only person in the car. " + " ".join(
            f"{n} as in [Image{i}], the same look as on their sheet." for i, n in
            enumerate(names, 1)),
        AUDIO,
    ])  # fmt: skip
    refs = [{"kind": "image", "id": cast[n][0], "role": f"{n}'s look"} for n in names]
    job = Job(workspace_id=project.workspace_id, kind="write-claude", provider="claude",
              project_id=pid, status=JobStatus.succeeded,
              input={"project_id": pid, "breakdown_id": bd.id, "step": "clip_prompts"},
              output={"clips": [{"clip_id": clip, "seconds": 8, "prompt": prompt,
                                 "references": refs}]})  # fmt: skip
    db.add(job)
    db.flush()
    clip_prompts.save_clip_prompts(db, job)
    db.commit()
    return db.query(ProjectClip).filter_by(project_id=pid, clip_id=clip).one()


def _take(editor, db, pid, row) -> str:
    """The files a new take of the clip is sent."""
    made = editor.post(f"/projects/{pid}/clips/{row.id}/generate")
    assert made.status_code == 201, made.text
    return json.dumps(db.get(Job, made.json()["id"]).input["files"])


def _off(editor, db, pid, shot: str, row) -> ProjectClip:
    """Danny taken out of `shot` (remove-ref), free: no writing job. The clip `row` after."""
    writes = db.query(Job).filter_by(project_id=pid, kind="write-claude").count()
    out = editor.post(f"/projects/{pid}/shots/{shot}/remove-ref",
                      json={"kind": "character", "name": "Danny"})  # fmt: skip
    assert out.status_code == 200, out.text
    db.expire_all()
    assert db.query(Job).filter_by(project_id=pid, kind="write-claude").count() == writes
    row = db.get(ProjectClip, row.id)
    assert row.breakdown_id == _plan(db, pid)[0].id  # moved with the plan: not stale
    return row


def test_a_person_only_named_in_the_lines_gets_no_role_and_no_sheet(owner, editor, db):
    pid, marcus = _video(owner, editor)
    assert editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"] == ["Marcus"]
    assert [r["role"] for r in editor.get(f"/projects/{pid}/assets").json()] == ["Marcus"]
    _, shows = _plan(db, pid)  # opening Assets put nobody in a talker shot
    assert all(who == [f"slot:{marcus}"] for who in shows.values()), shows
    _cast(editor, db, pid)
    looks = db.query(LibraryItem).filter_by(owner_project_id=pid).all()
    assert [i.name for i in looks] == ["Marcus"]  # one sheet drawn: no Danny's


def test_a_person_the_plan_puts_on_screen_gets_a_role_only_in_the_shots_that_show_him(
    owner, editor, db
):
    pid, marcus = _video(owner, editor, broll=True)
    assert sorted(editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"]) == [
        "Danny", "Marcus"]  # fmt: skip
    danny = next(r["slot_id"] for r in editor.get(f"/projects/{pid}/assets").json()
                 if r["role"] == "Danny")  # fmt: skip
    _, shows = _plan(db, pid)
    assert [s for s, who in shows.items() if f"slot:{danny}" in who] == ["2.2", "3.2"]
    assert shows["1.2"] == shows["4.1"] == shows["5.1"] == [f"slot:{marcus}"]


def test_the_talker_clips_prompt_and_take_carry_only_marcus(owner, editor, db):
    pid, _ = _video(owner, editor, broll=True)  # Danny is a role with a sheet (his B-roll)
    cast = _cast(editor, db, pid)
    row = _write(db, pid, cast, "c1", ["Marcus", "Danny"])  # as 315's writer attached him
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    assert "Danny as in" not in row.prompt and "is Danny" not in row.prompt
    assert "one Marcus, the only person in the car" in row.prompt
    sent = _take(editor, db, pid, row)
    assert str(cast["Marcus"][1]) in sent and str(cast["Danny"][1]) not in sent


def test_taking_a_person_out_of_a_shot_takes_him_off_the_clip_for_free(owner, editor, db):
    pid, _ = _video(owner, editor, broll=True)
    cast = _cast(editor, db, pid)
    bd, _ = _plan(db, pid)  # as 315's plan came to have it: Danny in shot 1.2
    data = json.loads(json.dumps(bd.data))
    data["scenes"][0]["shots"][1]["character_ids"].append(cast["Danny"][0])
    assert editor.put(f"/projects/{pid}/breakdown", json=data).status_code == 200
    row = _write(db, pid, cast, "c1", ["Marcus", "Danny"])
    assert cast["Danny"][0] in [r["id"] for r in row.references]
    row = _off(editor, db, pid, "1.2", row)
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    assert "Danny as in" not in row.prompt and "is Danny" not in row.prompt
    editor.get(f"/projects/{pid}/assets")  # opening Assets never puts him back
    assert _plan(db, pid)[1]["1.2"] == [cast["Marcus"][0]]


def test_a_person_the_plan_lists_gets_his_sheet_and_stays_out_once_taken_out(owner, editor, db):
    """ "Danny hands him the phone", Danny in the shot's list: his sheet goes with the clip
    and its take, though the writer left him out. Taken out of the shot, he's off the clip
    and stays out, though the words still show him: the list is who the shot shows."""
    pid, _ = _video(owner, editor, hands=True)
    cast = _cast(editor, db, pid)
    _, shows = _plan(db, pid)
    assert [s for s, who in shows.items() if cast["Danny"][0] in who] == ["4.1"]
    row = _write(db, pid, cast, "c4", ["Marcus"])
    assert [r["id"] for r in row.references] == [cast["Marcus"][0], cast["Danny"][0]]
    assert "Danny as in [Image2]" in row.prompt
    assert str(cast["Danny"][1]) in _take(editor, db, pid, row)
    row = _off(editor, db, pid, "4.1", row)
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    assert "Danny as in" not in row.prompt and "is Danny" not in row.prompt
    editor.get(f"/projects/{pid}/assets")  # opening Assets never puts him back
    assert _plan(db, pid)[1]["4.1"] == [cast["Marcus"][0]]


def test_an_insert_that_lists_nobody_never_pulls_in_who_its_words_name(owner, editor, db):
    """In a plan that lists who each shot shows, an empty list shows nobody: "a text from
    Danny" on the phone, in two clips, makes Danny no role and puts him in no shot."""
    pid, _ = _video(owner, editor, inserts=True)
    assert editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"] == ["Marcus"]
    _, shows = _plan(db, pid)
    assert shows["2.2"] == shows["3.2"] == []


def _land(owner, editor, db, brief: str, who: list[str], action: str = ""):
    """315's video with `brief`, its shot 2.1 listing `who` too (and doing `action`), landed
    as a plan is saved: the video's roles, what shot 2.1 shows, and the notes."""
    pid, _ = _video(owner, editor)
    project = db.get(Project, pid)
    project.goal = brief
    db.commit()
    plan = Breakdown.model_validate(_plan(db, pid)[0].data)
    plan.scenes[0].shots[2].character_ids += who
    plan.scenes[0].shots[2].action = action or plan.scenes[0].shots[2].action
    plan, notes = breakdown.land(db, project, plan)
    roles = [s.role for s in all_slots(db, project)]
    return roles, plan.scenes[0].shots[2].character_ids, notes


def test_an_extra_the_brief_describes_is_never_a_paid_role(owner, editor, db):
    """QA on #1496 (#1405, rule 7): "A woman, 30s, in a red dress" and "the bartender, 40s"
    listed as person:Woman and person:Bartender stay extras, drawn as part of the scene."""
    brief = "A woman, 30s, in a red dress walks past. The bartender, 40s, bald, pours."
    roles, shown, notes = _land(owner, editor, db, brief, ["person:Woman", "person:Bartender"])
    assert roles == ["Marcus"] and len(shown) == 1
    assert "Advice: Woman is on screen with no role." in notes
    assert "Advice: Bartender is on screen with no role." in notes


def test_an_extra_the_brief_writes_like_a_name_is_still_never_a_paid_role(owner, editor, db):
    """QA on #1496: a brief that opens on "Woman, 30s, …" or writes "Bartender (40s, bald)",
    while the plan says "a woman" and "the bartender": a word written in lowercase anywhere is
    never a name, so they stay extras."""
    action = "Behind Marcus, a woman in a red dress walks past and the bartender pours."
    for brief in ("Woman, 30s, in a red dress, walks past. Bartender, 40s, bald, pours.",
                  "Woman (30s, red dress) walks past. Bartender (40s, bald) pours."):  # fmt: skip
        roles, shown, notes = _land(owner, editor, db, brief,
                                    ["person:Woman", "person:Bartender"], action)  # fmt: skip
        assert roles == ["Marcus"] and len(shown) == 1, brief
        assert "Advice: Woman is on screen with no role." in notes, brief


def test_someone_the_plan_lists_and_the_brief_names_and_describes_is_a_role(owner, editor, db):
    """Video 294: the plan lists person:Maya, whom the script never names, and the brief says
    "his owner Maya, 30s": she's a role in that shot, so she gets a look."""
    brief = ("A song from Bruno's point of view (a young pitbull with a white chest blaze and a "
             "red collar; his owner Maya, 30s).")  # fmt: skip
    roles, shown, _ = _land(owner, editor, db, brief, ["person:Maya"])
    assert roles == ["Marcus", "Maya"]
    assert len(shown) == 2 and shown[-1].startswith("slot:")  # her role, in the shot


def test_a_brief_that_opens_on_the_names_makes_them_roles(owner, editor, db):
    """QA on #1496: a brief introduces people at the start of a sentence ("Bruno, a young
    pitbull…", "Maya, 30s, …"); listed as person:Bruno and person:Maya, both are roles."""
    brief = ("Brief: Bruno, a young pitbull with a red collar, chews his paw at night. Maya, "
             "30s, heavy-set, opens the bag.")  # fmt: skip
    roles, shown, _ = _land(owner, editor, db, brief, ["person:Bruno", "person:Maya"])
    assert roles == ["Marcus", "Bruno", "Maya"]
    assert len(shown) == 3 and all(r.startswith("slot:") for r in shown)


def test_a_shot_listing_nobody_that_shows_a_roles_hand_gets_that_role(owner, editor, db):
    """A plan written before it was asked to list someone seen only in part: "Danny's hand
    slides his phone across the table" lists nobody, so Danny, a role from his B-roll, joins
    that shot only, and his sheet goes with its clip."""
    pid, _ = _video(owner, editor, broll=True, part=True)
    cast = _cast(editor, db, pid)
    _, shows = _plan(db, pid)
    assert shows["4.2"] == [cast["Danny"][0]] and shows["4.1"] == [cast["Marcus"][0]]
    assert shows["2.1"] == shows["3.1"] == [cast["Marcus"][0]]
    row = _write(db, pid, cast, "c4", ["Marcus"])
    assert [r["id"] for r in row.references] == [cast["Marcus"][0], cast["Danny"][0]]
    row = _off(editor, db, pid, "4.2", row)  # the owner takes him out: he stays out
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    editor.get(f"/projects/{pid}/assets")
    assert _plan(db, pid)[1]["4.2"] == []


def test_a_speaker_taken_out_of_a_shot_stays_out(owner, editor, db):
    """Remove-ref on someone who speaks in the shot (a voice on the phone, say): opening Cast
    never puts them back."""
    pid, _ = _video(owner, editor, broll=True)
    cast = _cast(editor, db, pid)
    out = editor.post(f"/projects/{pid}/shots/1.1/remove-ref",
                      json={"kind": "character", "name": "Marcus"})  # fmt: skip
    assert out.status_code == 200, out.text
    editor.get(f"/projects/{pid}/assets")
    assert _plan(db, pid)[1]["1.1"] == [] and _plan(db, pid)[1]["1.2"] == [cast["Marcus"][0]]
