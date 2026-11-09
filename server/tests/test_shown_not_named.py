"""Video 315: Marcus, alone in his car, says "Danny" three times, and Danny is never on screen.
The director's plan kept Marcus alone in every talker shot, yet Danny was made a role, drawn,
and attached to clips 1, 4 and 5. A clip gets a person's sheet only when its shots show them
(Reed, 9 Nov: trust the plan), never because a line names them. No paid calls: the
stand-ins only."""

import json

from app import clip_prompts
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
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
BROLL = [  # 293's: Danny at the Thanksgiving table, in two clips
    ("2.2", "c2", "At the table, quiet Danny in a grey sweater hunches over his phone."),
    ("3.2", "c3", "Danny sets his phone face-down next to his plate, his ears going red."),
]
C1 = "\n".join([  # the clip prompt 315 saved for clip 1, Danny attached
    "Audio: only the spoken lines and the quiet inside of a parked car. No subtitles.",
    "References: [Image1] is Marcus. [Image2] is Danny.",
    "Summary: In his parked car, Marcus confesses he owes his brother-in-law an apology.",
    f'Shot 1 | 0-3 s. Selfie medium close-up. Marcus: "{LINES[0]}" Only Marcus speaks.',
    f'Shot 2 | 3-8 s. Same selfie. Marcus: "{LINES[1]}" Only Marcus speaks.',
    "Keep: Marcus as in [Image1], the same look as on their sheet; one Marcus, the only "
    "person in the car. Danny as in [Image2], the same look as on their sheet.",
    "Audio: only the spoken lines and the quiet inside of a parked car. No subtitles.",
])  # fmt: skip


def _shot(sid, lines, action, who):
    line = " ".join(LINES[n - 1] for n in lines) if lines else None
    return {"id": sid, "script_lines": lines, "speaker": "Marcus" if lines else None,
            "line": line, "action": action, "reaction": None, "camera": "Selfie close-up",
            "seconds": 3, "character_ids": who, "place_id": None, "moment": None,
            "screen_ids": []}  # fmt: skip


def _video(owner, editor, broll: bool) -> tuple[int, int]:
    """315's video from a published script (with 293's B-roll of Danny when `broll`): its id
    and Marcus's role."""
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    marcus = owner.post(f"{base}/cast", json={"role": "Marcus"}).json()[-1]["id"]
    shots = [(sid, clip, _shot(sid, lines, action, [f"slot:{marcus}"]))
             for sid, clip, lines, action in TALKER]  # fmt: skip
    shots += [(sid, clip, _shot(sid, [], action, [])) for sid, clip, action in BROLL if broll]
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


def _write_c1(db, pid, cast) -> ProjectClip:
    """Clip 1's prompt, as 315's writer answered it (Danny attached), saved as the worker
    saves it."""
    project, (bd, _) = db.get(Project, pid), _plan(db, pid)
    refs = [{"kind": "image", "id": cast[n][0], "role": f"{n}'s look"} for n in ("Marcus", "Danny")]
    job = Job(workspace_id=project.workspace_id, kind="write-claude", provider="claude",
              project_id=pid, status=JobStatus.succeeded,
              input={"project_id": pid, "breakdown_id": bd.id, "step": "clip_prompts"},
              output={"clips": [{"clip_id": "c1", "seconds": 8, "prompt": C1,
                                 "references": refs}]})  # fmt: skip
    db.add(job)
    db.flush()
    clip_prompts.save_clip_prompts(db, job)
    db.commit()
    return db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()


def test_a_person_only_named_in_the_lines_gets_no_role_and_no_sheet(owner, editor, db):
    pid, marcus = _video(owner, editor, broll=False)
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
    row = _write_c1(db, pid, cast)
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    assert "Danny as in" not in row.prompt and "is Danny" not in row.prompt
    assert "one Marcus, the only person in the car" in row.prompt
    made = editor.post(f"/projects/{pid}/clips/{row.id}/generate")
    assert made.status_code == 201, made.text
    sent = json.dumps(db.get(Job, made.json()["id"]).input["files"])
    assert str(cast["Marcus"][1]) in sent and str(cast["Danny"][1]) not in sent


def test_taking_a_person_out_of_a_shot_takes_him_off_the_clip_for_free(owner, editor, db):
    pid, marcus = _video(owner, editor, broll=True)
    cast = _cast(editor, db, pid)
    bd, _ = _plan(db, pid)  # as 315's plan had it: Danny in shot 1.2
    data = json.loads(json.dumps(bd.data))
    data["scenes"][0]["shots"][1]["character_ids"].append(cast["Danny"][0])
    assert editor.put(f"/projects/{pid}/breakdown", json=data).status_code == 200
    row = _write_c1(db, pid, cast)
    assert cast["Danny"][0] in [r["id"] for r in row.references]
    writes = db.query(Job).filter_by(project_id=pid, kind="write-claude").count()
    out = editor.post(f"/projects/{pid}/shots/1.2/remove-ref",
                      json={"kind": "character", "name": "Danny"})  # fmt: skip
    assert out.status_code == 200, out.text
    db.expire_all()
    row = db.get(ProjectClip, row.id)
    assert [r["id"] for r in row.references] == [cast["Marcus"][0]]
    assert "Danny as in" not in row.prompt and "is Danny" not in row.prompt
    assert row.breakdown_id == _plan(db, pid)[0].id  # moved with the plan: not stale
    assert db.query(Job).filter_by(project_id=pid, kind="write-claude").count() == writes  # free
    editor.get(f"/projects/{pid}/assets")  # opening Assets never puts him back
    assert _plan(db, pid)[1]["1.2"] == [cast["Marcus"][0]]
