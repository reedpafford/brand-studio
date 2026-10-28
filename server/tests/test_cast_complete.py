"""Every speaker is a role at Assets, and nothing is drawn without a look for everyone in the
shot (Reed, 2026-10-27, "Marriage Rejection": only the bride was a role, so the video model
invented the groom). The server adds the roles the cast read missed and puts each
in the shots it speaks on screen in; Storyboard and Clips wait for their looks, pointing to
Assets."""

import copy

from sqlalchemy import select

from app import breakdown
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import _make
from tests.test_unknown_cast import _look

TEXT = "INT. CHURCH — DAY\nNATE: Will you marry me?\nBRIDE: Hell no!\nNATE (V.O.): Day one."


def _video(owner, editor):
    """A published script whose cast read found only the bride; Nate speaks in shot 1.1 and
    over shot 1.2 (V.O.), and no shot shows him."""
    made = _make(owner, title="Marriage Rejection", text=TEXT)
    base = f"/scripts/{made['id']}"
    bride = owner.post(f"{base}/cast", json={"role": "Bride"}).json()[0]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    one, two = bd["scenes"][0]["shots"]
    one.update(script_lines=[2], speaker="Nate", line="Will you marry me?", character_ids=[])
    two.update(script_lines=[3, 4], speaker="Nate", line="Day one.",
               character_ids=[f"slot:{bride}"])  # fmt: skip
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return base, editor.post(f"{base}/drafts/0/produce").json()["project_id"], bride


def _fill(db):
    """What the cast read leaves for the server to do: add the speakers each script missed, then
    put every role in the shots it speaks in. One plain line per change."""
    out = []
    live = select(Script).where(Script.deleted_at.is_(None), Script.archived.is_(False))
    for script in db.scalars(live).all():
        out += [
            f"{script.title}: added {name} to the cast"
            for name in breakdown.add_speakers(db, script)
        ]
    for project in db.scalars(select(Project).where(Project.script_draft_id.is_not(None))).all():
        out += [x for x in breakdown.complete_cast(db, project) if not x.endswith(" to the cast")]
    db.commit()
    return out


def _who(editor, pid):
    plan = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]
    return [s["character_ids"] for s in plan["scenes"][0]["shots"]]


def test_missed_speakers_are_added_and_shown_where_they_speak(owner, editor, db):
    base, pid, bride = _video(owner, editor)
    row = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    on = {"1.1": True, "1.2": True}  # offered while nobody was in 1.1
    clip = ProjectClip(project_id=pid, breakdown_id=row.id, clip_id="c1", seconds=5, prompt="x",
                       references=[], real_images=on)  # fmt: skip
    db.add(clip)
    db.commit()
    clip = clip.id
    jobs = db.query(Job).count()
    said = _fill(db)
    nate = next(s["id"] for s in owner.get(base).json()["cast"] if s["role"] == "Nate")
    name = db.get(Project, pid).name
    assert said == ["Marriage Rejection: added Nate to the cast",
                    f"{name}: Nate now appears in 1 shot.",
                    f"{name}: turned off Use the real image on 1 shot with a person"]  # fmt: skip
    assert db.get(ProjectClip, clip).real_images == {"1.2": True}  # its shot didn't change
    assert _who(editor, pid) == [[f"slot:{nate}"], [f"slot:{bride}"]]  # not over his V.O.
    roles = [r["role"] for r in editor.get(f"/projects/{pid}/assets").json() if r["slot_id"]]
    assert roles == ["Bride", "Nate"]
    assert _fill(db) == []  # once only
    assert db.query(Job).count() == jobs  # free: no model call


def test_storyboard_and_clips_wait_for_every_look_naming_them(owner, editor, db):
    _, pid, bride = _video(owner, editor)  # opening Assets adds Nate, as the deploy does
    nate = next(r["slot_id"] for r in editor.get(f"/projects/{pid}/assets").json()
                if r["role"] == "Nate")  # fmt: skip
    board, clips = f"/projects/{pid}/storyboard", f"/projects/{pid}/clips/prompts"
    for url in (board, clips):
        refused = editor.post(url, json={})
        assert refused.status_code == 409
        assert refused.json()["detail"] == (
            "Nate and Bride have no approved look yet. Approve them in Assets."
        )
    for slot, name in ((bride, "Bride look"), (nate, "Nate look")):
        look = {"library_item_id": _look(owner, db, name)}
        assert editor.put(f"/projects/{pid}/assets/slots/{slot}", json=look).status_code == 200
    assert editor.post(board, json={}).status_code == 201


def test_a_role_joins_the_shots_naming_it_but_not_its_off_screen_lines(owner, editor, db):
    _, pid, _ = _video(owner, editor)
    _fill(db)
    project = db.get(Project, pid)
    plan = Breakdown.model_validate(editor.get(f"/projects/{pid}/breakdown").json()["breakdown"])
    one, two = plan.scenes[0].shots
    one.character_ids = []
    off = TEXT.replace("NATE: Will", "NATE (O.S.): Will")
    assert breakdown.show_roles(db, project, plan, off) == {}
    two.action = "The bride stares at Nate's ring."
    assert breakdown.show_roles(db, project, plan, off) == {"1.2": ["Nate"]}


def test_a_label_naming_a_role_already_there_never_makes_a_second_one(owner, editor, db):
    """One person is never two roles: "GROOM:" is "Nate, the teen groom"."""
    made = _make(owner, title="Altar", text="INT. CHURCH — DAY\nGROOM: Will you marry me?")
    base = f"/scripts/{made['id']}"
    nate = owner.post(f"{base}/cast", json={"role": "Nate, the teen groom"}).json()[0]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0].update(script_lines=[2], speaker="Groom", character_ids=[])
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    name = db.get(Project, pid).name  # shot 1.2's speaker is Nate too
    shown = f"{name}: Nate now appears in 2 shots."
    assert _fill(db) == [shown]
    assert [s["role"] for s in owner.get(base).json()["cast"]] == ["Nate, the teen groom"]
    assert _who(editor, pid)[0] == [f"slot:{nate}"]


def test_a_name_inside_a_roles_description_is_never_that_role(owner, editor, db):
    """QA on #614: NATE is not "Kimchi, Nate's rich friend" (nor MALIK "Dre, Malik's best
    friend"), so Nate becomes his own role and Kimchi stays out of Nate's shot."""
    from app.cast_roles import labels

    assert not labels("NATE", "Kimchi, Nate's rich friend")
    assert not labels("MALIK", "Dre, Malik's best friend")
    assert labels("GROOM", "Nate, the teen groom") and labels(
        "KIMCHI", "Kimchi, Nate's rich friend"
    )
    made = _make(owner, title="Rich", text="INT. CAR — DAY\nNATE: Nice car.\nKIMCHI: I know.")
    base = f"/scripts/{made['id']}"
    kimchi = owner.post(f"{base}/cast", json={"role": "Kimchi, Nate's rich friend"}).json()
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0].update(script_lines=[2], speaker="Nate", character_ids=[])
    bd["scenes"][0]["shots"][1].update(script_lines=[3], speaker="Kimchi", character_ids=[])
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    _fill(db)
    cast = owner.get(base).json()["cast"]
    assert [s["role"] for s in cast] == ["Kimchi, Nate's rich friend", "Nate"]
    assert _who(editor, pid) == [[f"slot:{cast[1]['id']}"], [f"slot:{kimchi[0]['id']}"]]


def test_storyboard_right_after_produce_waits_without_assets_being_opened(owner, editor, db):
    """QA-2 on #614: the gate never depends on a page being opened."""
    _, pid, _ = _video(owner, editor)
    refused = editor.post(f"/projects/{pid}/storyboard", json={})
    assert refused.status_code == 409 and "Nate and Bride" in refused.json()["detail"]


def test_versions_naming_one_person_differently_are_flagged_never_merged(owner, db):
    """QA-Live, Marriage Rejection: version A says GROOM, B says NOAH for the same man, so
    the backstop made two roles. They're flagged as maybe one person, for a click to merge."""
    made = _make(owner, title="Altar", text="INT. CHURCH — DAY\nGROOM: Will you marry me?")
    base = f"/scripts/{made['id']}"
    owner.put(f"{base}/drafts/1", json={"text": "INT. CHURCH — DAY\nNOAH: Will you marry me?"})
    _fill(db)
    cast = {s["role"]: s["id"] for s in owner.get(base).json()["cast"]}
    assert set(cast) == {"Groom", "Noah"}  # never merged by itself
    pairs = owner.get(base).json()["maybe_same"]
    assert [(p["a_slot_id"], p["b_slot_id"], p["into_slot_id"]) for p in pairs] == [
        (cast["Groom"], cast["Noah"], cast["Groom"])
    ]
    assert pairs[0]["why"] == "They say the same line in different versions of the script."


def test_a_role_this_video_never_shows_needs_no_look_here(owner, editor, db):
    _, pid, _ = _video(owner, editor)
    project = db.get(Project, pid)
    draft = db.get(ScriptDraft, project.script_draft_id)
    db.add(ScriptCastSlot(script_id=draft.script_id, role="Rival", position=9))
    db.commit()
    rows = {r["role"]: r for r in editor.get(f"/projects/{pid}/assets").json() if r["slot_id"]}
    assert (rows["Rival"]["shots"], rows["Rival"]["ready"]) == (0, True)
    missing = editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"]
    assert "Rival" not in missing and set(missing) == {"Bride", "Nate"}


def test_another_versions_role_is_not_listed_on_this_videos_assets(owner, editor, db):
    """QA-Live run 3: video A (classroom) listed B's gym bro and C's uncle as missing, and
    Approve all listed them as skipped."""
    _, pid, _ = _video(owner, editor)
    draft = db.get(ScriptDraft, db.get(Project, pid).script_draft_id)
    db.add(ScriptCastSlot(script_id=draft.script_id, role="Gym bro", position=9, appears_in=[1]))
    db.add(ScriptCastSlot(script_id=draft.script_id, role="Teacher", position=10,
                          appears_in=[draft.slot]))  # fmt: skip
    db.commit()
    roles = [r["role"] for r in editor.get(f"/projects/{pid}/assets").json() if r["slot_id"]]
    assert "Gym bro" not in roles and "Teacher" in roles  # this version's, even with no shot


def test_script_twos_versions_flag_both_pairs_and_a_one_version_echo_flags_none(owner, db):
    """QA on #628, script 2's shape: A says GROOM/BRIDE, B NOAH/GIRLFRIEND, C BRIDE/NOAH, and
    no line is said word for word twice. BRIDE in A and C talks to GROOM and to NOAH; NOAH in
    B and C talks to GIRLFRIEND and to BRIDE. Flagged, never merged."""
    versions = [
        "INT. CHURCH — DAY\nGROOM: Will you marry me?\nBRIDE: I can't do this. I don't love you.",
        "INT. PARK — DAY\nNOAH: Babe, marry me?\nGIRLFRIEND: Never. We're done.",
        "INT. CHURCH — DAY\nNOAH: Marry me?\nBRIDE: No. I don't love you anymore.",
    ]
    base = f"/scripts/{_make(owner, title='Marriage Rejection', text=versions[0])['id']}"
    for slot in (1, 2):
        owner.put(f"{base}/drafts/{slot}", json={"text": versions[slot]})
    _fill(db)
    script = owner.get(base).json()
    cast = {s["role"]: s["id"] for s in script["cast"]}
    assert set(cast) == {"Groom", "Bride", "Noah", "Girlfriend"}  # nothing merged
    why = "Both are the one {} speaks to in different versions."
    assert {(p["a_slot_id"], p["b_slot_id"], p["why"]) for p in script["maybe_same"]} == {
        (cast["Groom"], cast["Noah"], why.format("Bride")),
        (cast["Bride"], cast["Girlfriend"], why.format("Noah")),
    }

    echo = _make(
        owner, title="Echo", text="INT. KITCHEN — DAY\nMOM: Are you sure?\nNATE: Are you sure?"
    )
    _fill(db)
    assert owner.get(f"/scripts/{echo['id']}").json()["maybe_same"] == []


def test_a_speaker_added_twice_at_once_is_added_once_without_an_error(
    owner, editor, db, monkeypatch
):
    """QA-2 on #659: Assets' parallel requests each ran the backstop, and the second one's
    insert of the same role failed with a 500."""
    from app import script_cast_read

    base, _, _ = _video(owner, editor)
    script = db.get(Script, owner.get(base).json()["id"])
    assert breakdown.add_speakers(db, script) == ["Nate"]
    db.commit()
    monkeypatch.setattr(script_cast_read, "_slots", lambda db, script: [])  # it hasn't seen Nate
    assert breakdown.add_speakers(db, script) == []
    db.commit()
    roles = [s.role for s in db.scalars(select(ScriptCastSlot).filter_by(script_id=script.id))]
    assert roles.count("Nate") == 1
