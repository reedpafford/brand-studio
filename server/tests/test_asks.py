"""The director asks (v6 piece B, S4-01 to S4-04, S3-05): its question cards in every state,
the run waiting on that point only, a story choice's pick after its time (rule 37), saved
answers reused, and the director's eyes on what it's given. All on the stand-ins."""

import copy
import json
import math
from datetime import timedelta

from app import ask_options, asks, director
from app import voices as saved_voices
from app.db import utcnow
from app.models.asks import Ask
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from tests.conftest import first_brand, upload
from tests.helpers import make_it, product, with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_director import _run
from tests.test_script_library import SCRIPT, _make

QUESTION = {"kind": "question", "topic": "Who it's for", "question": "Who's this for?",
            "why": "It changes the hook."}  # fmt: skip


def _video(app, owner, editor, db) -> tuple[int, int]:
    """A published script's video with Mom locked to Mia and Nate not cast yet; the brand
    has Kid saved (with a sheet)."""
    app.state.settings.fake_providers = True
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    nate = owner.post(f"{base}/cast", json={"role": "Nate", "description": "teen"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia.json()["id"]})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia.json()['id']}", f"slot:{nate}"]
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    brand = db.get(Project, pid).brand_id
    kid = owner.post("/library/character", json={"name": "Kid", "brand_ids": [brand],
                                                 "image_file_ids": [upload(owner)]})  # fmt: skip
    with_sheet(db, kid.json()["id"])
    return pid, kid.json()["id"]


def _ask(db, pid, move) -> Ask:
    project = db.get(Project, pid)
    said = asks.asked(db, project, None, move)
    assert said.startswith("Asked: "), said
    return db.query(Ask).order_by(Ask.id.desc()).first()


def _dollars(value) -> list:
    """Every dollar figure in a response (editors see credits only, rule 4)."""
    if isinstance(value, dict):
        return [v for k, v in value.items() if k == "usd" and v is not None] + [
            x for v in value.values() for x in _dollars(v)]  # fmt: skip
    return [x for v in value for x in _dollars(v)] if isinstance(value, list) else []


def _card(client, ask: Ask) -> dict:
    return next(a for a in client.get(f"/projects/{ask.project_id}/asks").json()
                if a["id"] == ask.id)  # fmt: skip


def asking(fake):
    """A stand-in director that asks `fake`'s question once Make it is pressed, then works as
    ever, but delivers only once every question is answered."""
    real = director.choose

    def choose(state):
        if state.get("started") is False or state.get("treatment") == "none":
            return real(state)
        if not state.get("asks"):
            return {"tool": "ask", "why": "all: only you know.", "ask": fake}
        move = real(state)
        if move["tool"] == "deliver" and any(a["state"] != "answered" for a in state["asks"]):
            return {**move, "tool": "wait", "why": "Waiting on your answer."}
        return move

    return choose


def test_it_asks_keeps_working_waits_only_on_that_then_goes_on(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(director, "choose", asking(QUESTION))
    pid, _ = _video(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "running" and [w["topic"] for w in out["waiting"]] == ["Who it's for"]
    tools = [t["tool"] for t in out["turns"]]
    assert tools.index("ask") < tools.index("final_cut")  # everything else carried on
    assert out["turns"][-1]["result"] == director.ON_YOU  # then it sleeps on that one point
    (card,) = editor.get(f"/projects/{pid}/asks").json()[1:]  # after its start card
    assert (card["kind"], card["state"], card["can"]) == ("question", "open", ["reply"])
    assert any(m["kind"] == "ask" and m["ask_id"] == card["id"] for m in out["thread"])
    turns = len(out["turns"])
    _run(app, db, ticks=5)
    assert len(editor.get(f"/projects/{pid}/director").json()["turns"]) == turns  # no turn
    r = editor.post(f"/asks/{card['id']}/answer", json={"how": "reply", "text": "Men 30-50."})
    assert r.status_code == 200 and r.json()["state"] == "answered", r.text
    assert r.json()["answered_by"] == "Ed" and r.json()["by_owner"] is False
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered" and out["waiting"] == [], out["ended"]
    prompt = db.query(Job).filter(Job.project_id == pid, Job.input["step"].as_string() == "director"
                                  ).order_by(Job.id.desc()).first().input["prompt"]  # fmt: skip
    assert "Men 30-50." in prompt.split("<asks>")[1]  # it read the answer


def test_a_saved_pick_casts_the_role_and_is_reused_next_time_without_asking(app, db, owner, editor):
    pid, kid = _video(app, owner, editor, db)
    move = {"kind": "cast", "topic": "Nate", "subject": "Nate", "question": "Who plays Nate?",
            "why": "He's in 2 of 2 clips.", "pick": "Kid"}  # fmt: skip
    ask = _ask(db, pid, move)
    card = _card(owner, ask)
    assert card["saved_in"].startswith("Saved in ") and card["pick"] == f"item:{kid}"
    saved = {s["id"]: s for s in card["saved"]}
    assert saved[f"item:{kid}"]["name"] == "Kid" and saved[f"item:{kid}"]["file_id"]
    assert set(card["can"]) == {"reply", "saved", "upload", "generate"}
    assert card["generate"]["credits"] > 0 and card["generate"]["usd"] > 0  # price first
    assert _card(editor, ask)["generate"]["usd"] is None  # editors: credits only (rule 4)
    assert _dollars(editor.get(f"/projects/{pid}/asks").json()) == []
    r = owner.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": f"item:{kid}"})
    assert r.json()["state"] == "answered" and r.json()["by_owner"] is True  # on Ed's video
    db.expire_all()
    project = db.get(Project, pid)
    nate = db.query(ScriptCastSlot).filter_by(role="Nate").one()
    assert project.slot_cast[str(nate.id)] == kid  # cast, free
    used = owner.get(f"/projects/{pid}/asks").json()[0]["saved"][0]
    assert (used["id"], used["used_in"]) == (f"item:{kid}", 1)  # "used in 1 video"

    other, _ = _video(app, owner, editor, db)  # the next video in the brand
    said = asks.asked(db, db.get(Project, other), None, move)
    brand = db.get(Brand, db.get(Project, other).brand_id)
    assert said == f"Kid is saved in {brand.name}, so I used that."
    nate = db.query(ScriptCastSlot).filter_by(role="Nate").order_by(ScriptCastSlot.id.desc())
    assert db.get(Project, other).slot_cast[str(nate.first().id)] == kid  # never asked again


def test_a_story_choice_shows_its_pick_and_goes_with_it_after_its_time(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    move = {
        "kind": "story",
        "topic": "How it ends",
        "question": "How should it end?",
        "choices": [
            {"title": "He bins the pint", "why": "Clear before and after."},
            {"title": "He toasts the camera", "why": "Funnier."},
        ],
        "pick": "A",
    }
    assert asks.asked(db, db.get(Project, pid), None, {**move, "choices": []}).startswith(
        "Refused")  # fmt: skip
    ask = _ask(db, pid, move)
    card = _card(owner, ask)
    assert card["pick"] == "A" and card["choices"][0]["why"] == "Clear before and after."
    assert card["decide_at"] and "choice" in card["can"] and "generate" not in card["can"]
    assert asks.overdue(db) == []  # not yet
    ask.decide_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert asks.overdue(db) == [pid]
    card = _card(owner, ask)
    assert card["state"] == "answered" and card["answer"]["how"] == "default"
    assert card["answered_by"] == "" and card["decide_at"] is None
    (said,) = asks.for_director(db, db.get(Project, pid))
    assert said["answer"] == "no answer by the time on the card: your pick He bins the pint"
    r = owner.post(f"/asks/{ask.id}/answer", json={"how": "choice", "choice": "B"})  # Change
    assert r.json()["answer"]["name"] == "He toasts the camera"


def test_generated_options_cost_their_price_stay_with_the_video_and_can_be_cancelled(
    app, db, owner, editor
):
    pid, _ = _video(app, owner, editor, db)
    move = {"kind": "cast", "subject": "Nate", "question": "Who plays Nate?",
            "describe": "a tired teen in a hoodie"}  # fmt: skip
    ask = _ask(db, pid, move)
    r = editor.post(f"/asks/{ask.id}/generate", json={})
    assert r.status_code == 200 and r.json()["state"] == "generating", r.text
    assert r.json()["can"][-1] == "cancel" and len(r.json()["options"]) == ask_options.OPTIONS
    jobs = db.query(Job).filter(Job.input["step"].as_string() == "ask_option").all()
    assert len(jobs) == 3 and "a tired teen in a hoodie" in jobs[0].input["input"]["prompt"]
    assert editor.post(f"/asks/{ask.id}/generate", json={}).status_code == 409  # one at a time
    r = editor.post(f"/asks/{ask.id}/cancel")
    assert r.json()["state"] == "open" and r.json()["options"] == []  # nothing was made
    db.expire_all()
    assert {j.status for j in db.query(Job).filter(Job.id.in_([j.id for j in jobs]))} == {
        JobStatus.cancelled
    }  # nothing charged

    editor.post(f"/asks/{ask.id}/generate", json={})
    _run(app, db, ticks=4)
    card = _card(editor, ask)
    assert card["state"] == "ready" and all(o["file_id"] for o in card["options"])
    assert card["options_spent"]["credits"] > 0
    r = editor.post(f"/asks/{ask.id}/generate", json={"like": 1, "change": "older"})
    newest = db.query(Job).filter(Job.input["step"].as_string() == "ask_option")
    newest = newest.order_by(Job.id.desc()).first()
    assert newest.input["files"]["image_input"] == [card["options"][1]["file_id"]]  # like 2
    _run(app, db, ticks=4)
    made = _card(editor, ask)["options"]
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "option", "option": 0})
    assert r.json()["answer"]["file_id"] == made[0]["file_id"]
    db.expire_all()
    nate = db.query(ScriptCastSlot).filter_by(role="Nate").one()
    look = db.get(LibraryItem, db.get(Project, pid).slot_cast[str(nate.id)])
    assert look.owner_project_id == pid and look.sheet_file_id == made[0]["file_id"]  # rule 12
    assert not look.brands  # never the brand's


def test_failed_options_charge_nothing_and_a_product_never_generates(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "place", "question": "Where's the kitchen?"})
    editor.post(f"/asks/{ask.id}/generate", json={})
    for job in db.query(Job).filter(Job.input["step"].as_string() == "ask_option"):
        job.status, job.credits = JobStatus.failed, 0  # the picture service made nothing
    db.commit()
    card = _card(editor, ask)
    assert (card["state"], card["options_spent"]["credits"]) == ("failed", 0)
    assert "generate" in card["can"]  # Try again, at its price
    product = _ask(db, pid, {"kind": "product", "question": "Is this the capsule?"})
    r = editor.post(f"/asks/{product.id}/generate", json={})
    assert r.status_code == 409 and "real product" in r.json()["detail"]
    assert _card(editor, product)["generate"] is None


def test_an_editors_options_past_the_budget_wait_on_the_card(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    ask = _ask(db, pid, {"kind": "cast", "subject": "Nate", "question": "Who plays Nate?"})
    card = editor.post(f"/asks/{ask.id}/generate", json={}).json()
    assert card["state"] == "held" and "cancel" in card["can"]
    assert not db.query(Ask).filter(Ask.kind == "budget").count()  # on its own card
    card = editor.post(f"/asks/{ask.id}/cancel").json()  # Withdraw
    assert card["state"] == "open"


def test_an_upload_is_kept_with_the_video_and_its_look_is_drawn_from_it(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "cast", "subject": "Nate", "question": "Who plays Nate?"})
    assert editor.post(f"/asks/{ask.id}/uploading", json={"on": True}).json()["state"] == (
        "uploading")  # fmt: skip
    assert editor.post(f"/asks/{ask.id}/uploading", json={"on": False}).json()["state"] == "open"
    sound = upload(editor, "a.mp3", b"ID3" + b"0" * 32, "audio/mpeg")
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "upload", "file_id": sound})
    assert r.status_code == 422  # a role takes a picture or a clip
    photo = upload(editor, "husband-ref.png")
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "upload", "file_id": photo})
    assert r.json()["answer"]["name"] == "husband-ref.png"
    db.expire_all()
    project = db.get(Project, pid)
    nate = db.query(ScriptCastSlot).filter_by(role="Nate").one()
    look = db.get(LibraryItem, project.slot_cast[str(nate.id)])
    assert look.source_photo_file_id == photo and not look.brands  # this video's only
    missing = editor.get(f"/projects/{pid}/assets/missing-looks").json()
    assert missing["roles"] == ["Nate"]  # make_looks draws its sheet from the photo
    editor.post(f"/projects/{pid}/assets/make-missing")
    sheet = db.query(Job).filter(Job.input["step"].as_string() == "sheet").one()
    assert sheet.input["library_item_id"] == look.id
    assert editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"] == []


def test_the_director_sees_what_its_given(app, db, owner, editor):
    """Eyes: an answer's picture, a picture sent in the chat and a clip go into its turn as
    images, each named in <seen>; a clip as frames."""
    import subprocess

    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "place", "question": "Where's the kitchen?"})
    photo = upload(editor, "kitchen.png")
    editor.post(f"/asks/{ask.id}/answer", json={"how": "upload", "file_id": photo})
    clip_path = f"{app.state.settings.storage_dir}/clip.mp4"
    made = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=d=1:s=64x64", clip_path]
    subprocess.run(made, check=True)  # noqa: S603, S607 - fixed arguments
    with open(clip_path, "rb") as f:
        clip = upload(editor, "walk.mp4", f.read(), "video/mp4")
    sent = editor.post(f"/projects/{pid}/director/messages",
                       json={"text": "Like this walk.", "files": [clip]})  # fmt: skip
    assert sent.status_code == 201, sent.text
    said = [m for m in sent.json()["thread"] if m["kind"] == "message"]
    assert said[-1]["files"] == [clip]
    db.expire_all()
    project = db.get(Project, pid)
    said = director.turn_input(db, project, {"id": "r", "turn": 1, "redos": {}, "by": 1})
    assert said["files"] == {"reference_images": [photo]} and said["clip_frames"] == [clip]
    seen = json.loads(said["prompt"].split("<seen>")[1].split("</seen>")[0])
    assert seen == [
        "Image 1: your answer to “Where's the kitchen?”",
        "Images 2-4: frames of a clip, sent in the chat: “Like this walk.”",
    ]
    from app.worker import _files_as_data

    job = Job(workspace_id=project.workspace_id, kind="write-claude", provider="claude",
              input={"step": "director", **said}, project_id=pid)  # fmt: skip
    given = _files_as_data(db, app.state.storage, job)["input"]["reference_images"]
    assert len(given) == 1 + director.FRAMES and given[-1].startswith("data:image/jpeg")


def test_no_longer_needed_and_a_stop_closes_what_it_asked(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    ask = _ask(db, pid, {"kind": "place", "question": "Which kitchen?"})
    said = asks.asked(db, project, None, {"ask_id": ask.id,
                                          "closed": "You locked the cast to Mark."})  # fmt: skip
    assert said == "No longer needed: Which kitchen?"
    card = _card(editor, ask)
    assert (card["state"], card["closed"], card["can"]) == (
        "not_needed", "You locked the cast to Mark.", [])  # fmt: skip
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "reply", "text": "Mine."})
    assert r.status_code == 409
    editor.post(f"/projects/{pid}/director")
    run = director.turns(db, project)[0].input[director.RUN]["id"]
    again = Ask(workspace_id=project.workspace_id, project_id=pid, run=run, kind="question",
                question="Who's it for?")  # fmt: skip
    db.add(again)
    db.commit()
    editor.post(f"/projects/{pid}/director/stop")
    db.expire_all()
    assert (db.get(Ask, again.id).state, db.get(Ask, again.id).closed) == (
        "not_needed", "The run was stopped.")  # fmt: skip


def test_the_start_card_waits_for_make_it_and_change_the_plan_first_keeps_it_waiting(
    app, db, owner, editor, monkeypatch
):
    from decimal import Decimal

    from app.settings import get_settings

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    monkeypatch.setattr(get_settings(), "plan_credits_before_ok", 30.0)  # room for a change
    pid, _ = _video(app, owner, editor, db)  # Ed's video from a published script, inside its
    # budget: he starts it himself (S2-06)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db, ticks=4, start=False)
    out = editor.get(url).json()
    assert (out["started"], out["status"]) == (False, "running")  # S3-02
    assert [t["tool"] for t in out["turns"]] == ["treatment", None]
    made = {j.input.get("step") for j in db.query(Job).filter(Job.project_id == pid)}
    assert made == {"director", "treatment"}  # its plan only: no generation started
    assert out["spent"] > 0  # the plan is charged as it costs, on its allowance
    (card,) = owner.get(f"/projects/{pid}/asks").json()
    assert card["kind"] == "start" and card["question"].startswith("Make it for up to $")
    assert card["can"] == ["make_it", "decline"]  # the owner, on Ed's video
    mine = editor.get(f"/projects/{pid}/asks").json()[0]
    assert mine["question"].endswith(" credits?") and mine["can"] == ["make_it"]
    assert mine["money"]["up_to"]["credits"] == math.ceil(out["run_price"])  # never below

    editor.post(f"{url}/messages", json={"text": "End on the capsule."})  # Change the plan first
    _run(app, db, ticks=6, start=False)
    cards = editor.get(f"/projects/{pid}/asks").json()
    assert [c["state"] for c in cards] == ["not_needed", "open"]  # a new card
    out = editor.get(url).json()
    assert out["started"] is False
    assert any("Note 1" in t["why"] for t in out["turns"] if t["tool"] == "treatment")
    r = editor.post(f"/asks/{cards[1]['id']}/answer", json={"how": "make_it"})
    assert r.status_code == 200 and r.json()["state"] == "answered", r.text
    _run(app, db)
    out = editor.get(url).json()
    assert out["status"] == "delivered" and out["started"] and out["spent"] > 0, out["ended"]


def test_an_editors_pasted_script_waits_for_the_owner_and_may_withdraw(app, db, owner, editor):
    """S4-02: an editor's send from pasted words is held for the owner after its treatment:
    "Waiting for the owner's OK" with Withdraw, in Needs you too; never Make it."""
    from tests.test_freestyle_dialogue import BODY

    app.state.settings.fake_providers = True
    sent = editor.post("/freestyles", json=BODY).json()
    _run(app, db, ticks=4, start=False)
    (row,) = editor.get("/needs-you").json()["money"]  # the editor's own request
    card = row["ask"]
    assert (card["kind"], card["can"]) == ("start", ["withdraw"])
    assert _dollars(row) == [] and card["question"].endswith(" credits?")
    assert editor.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 403
    (mine,) = owner.get("/needs-you").json()["money"]
    assert mine["ask"]["can"] == ["make_it", "decline"] and "$" in mine["ask"]["question"]
    r = editor.post(f"/asks/{card['id']}/answer", json={"how": "withdraw"})
    assert r.json()["state"] == "not_needed"
    assert editor.get(f"/freestyles/{sent['id']}").json()["status"] == "withdrawn"


def test_past_the_budget_the_owner_approves_or_keeps_it_and_editors_see_credits(
    app, db, owner, editor
):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    first = editor.post(f"/projects/{pid}/plan")  # an editor's press past the budget: held
    assert first.json()["status"] == "needs_owner_approval"
    (card,) = owner.get(f"/projects/{pid}/asks").json()
    assert card["kind"] == "budget" and card["can"] == ["approve", "keep"]
    assert card["question"].endswith("past the budget.") and "$" in card["question"]
    assert "spent plus up to" in card["why"]
    seen = editor.get(f"/projects/{pid}/asks").json()[0]
    assert "credits past the budget." in seen["question"] and seen["can"] == ["withdraw"]
    assert seen["why"].endswith("The owner has been asked; nothing is charged while it waits.")
    assert _dollars(seen) == []
    r = owner.post(f"/asks/{card['id']}/answer", json={"how": "keep"})
    assert r.json()["state"] == "answered" and r.json()["can"] == []
    assert db.get(Job, first.json()["id"]).status == JobStatus.cancelled  # nothing charged
    again = editor.post(f"/projects/{pid}/plan").json()  # a new hold: a new card
    cards = owner.get(f"/projects/{pid}/asks").json()
    assert [c["state"] for c in cards] == ["answered", "open"]
    owner.post(f"/jobs/{again['id']}/approve")  # through the old route: the card follows
    assert owner.get(f"/projects/{pid}/asks").json()[1]["state"] == "answered"


def test_needs_you_lists_questions_money_and_stuck_across_brands(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    ask = _ask(db, pid, QUESTION)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    editor.post(f"/projects/{pid}/plan")  # held: Money
    stuck, _ = _video(app, owner, editor, db)
    db.add(Job(workspace_id=project.workspace_id, kind="video", provider="fake",
               input={"step": "clip_take"}, project_id=stuck, status="failed",
               error="The model makes 12 s at most."))  # fmt: skip
    db.commit()
    out = owner.get("/needs-you").json()
    assert out["total"] == 3
    assert [r["ask"]["id"] for r in out["questions"]] == [ask.id]
    assert out["questions"][0]["video"]["made_by"] == "Ed"
    assert [r["ask"]["kind"] for r in out["money"]] == ["budget"]
    (row,) = out["stuck"]
    assert (row["video"]["id"], row["why"]) == (stuck, "The model makes 12 s at most.")
    assert row["fix"]["label"] in ("Make it again", "Open the chat")
    brand = first_brand(owner)
    counts = {b["id"]: b["count"] for b in out["brands"]}
    assert counts[project.brand_id] == 3 and all(
        c == 0 for b, c in counts.items() if b != project.brand_id)  # fmt: skip
    other = next(b for b in out["brands"] if b["id"] != project.brand_id)
    filtered = owner.get("/needs-you", params={"brand_id": other["id"]}).json()
    assert filtered["questions"] == filtered["money"] == filtered["stuck"] == []
    assert filtered["total"] == 3 and brand  # counts stay whole
    r = owner.post(f"/asks/{ask.id}/answer", json={"how": "reply", "text": "Everyone bloated."})
    assert r.json()["by_owner"] is True  # the same answer as in the chat
    assert owner.get("/needs-you").json()["questions"] == []
    assert _dollars(editor.get("/needs-you").json()) == []


def test_a_voice_card_offers_the_voices_free_to_play_and_a_sample_upload(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?",
                         "pick": "Roger"})  # fmt: skip
    card = _card(owner, ask)
    voices = {s["name"]: s for s in card["saved"]}
    assert voices["Roger"]["note"].startswith("Relaxed man") and card["pick"] == "stock:Roger"
    assert any(v["name"] == "Dr. Pickle" and v["id"].startswith("voice:") for v in card["saved"])
    assert card["generate"] is None and {"upload", "clone"} <= set(card["can"])
    assert card["clone"]["credits"] > 0 and card["clone"]["usd"] > 0  # "Clone it once · up to"
    assert _card(editor, ask)["clone"]["usd"] is None  # editors: credits only
    photo = upload(editor)
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "upload", "file_id": photo})
    assert r.status_code == 422  # a voice takes a sample
    sample = upload(editor, "voice.mp3", b"ID3" + b"0" * 32, "audio/mpeg")
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "upload", "file_id": sample})
    assert r.json()["answer"]["file_id"] == sample  # kept with this video
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": "stock:Roger"})
    assert r.json()["answer"]["name"] == "Roger"  # changed after answering
    db.expire_all()
    video = db.get(Project, pid)
    assert video.voice == "stock:Roger" and saved_voices.picked(db, video) == "Roger"  # read in it
    assert video.settings_log[-1]["by"] == "person"  # the person's: the director keeps it


def test_a_voice_card_clones_a_sample_once_at_its_price(app, db, owner, editor):
    """S4-01's "Upload a sample · Clone it once · up to $3.00", through #1314's clone: an
    editor's waits for the owner's OK, and the narration then reads "voice:<id>"."""
    import subprocess

    from app.models.jobs import JobStatus

    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    path = f"{app.state.settings.storage_dir}/sample.mp3"
    made = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=12", path]
    subprocess.run(made, check=True)  # noqa: S603, S607 - fixed arguments
    with open(path, "rb") as f:
        sample = upload(editor, "nate.mp3", f.read(), "audio/mpeg")
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": sample,
                                                     "text": "Nate"})  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["answer"]["option"].startswith("voice:")
    assert r.json()["state"] == "held"  # an editor's clone waits for the owner's OK
    db.expire_all()
    clone = db.query(Job).filter(Job.kind == "voice").one()
    assert clone.status == JobStatus.needs_owner_approval
    assert saved_voices.picked(db, db.get(Project, pid)) is None  # not read until it's cloned
    again = editor.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": sample})
    assert again.status_code == 409  # one charge a sample
    clone.status, clone.error = JobStatus.failed, "The voice couldn't be cloned."
    db.commit()
    assert _card(editor, ask)["state"] == "failed"  # nothing charged: answer it again
    retry = editor.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": sample})
    assert retry.status_code == 200 and retry.json()["state"] == "held"
    hope = asks.asked(db, db.get(Project, pid), None, {"kind": "voice", "subject": "Hope",
                                                        "question": "Hope's voice?"})  # fmt: skip
    assert hope == "Asked: Hope's voice?"  # an app voice's name is never taken as an answer


def test_describe_it_saves_a_brand_voice_read_in_the_nearest_app_voice(app, db, owner, editor):
    """Reed, 6 Nov: S4-01's "Describe it" makes no voice and costs nothing: the words pick the
    nearest app voice, saved to the brand as a described voice (S8-04) and used for this
    video; the card's other ways stay."""
    from app.models.voices import Voice

    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    card = _card(editor, ask)
    assert "describe" in card["can"] and "reply" not in card["can"] and "clone" in card["can"]
    jobs = db.query(Job).count()
    empty = editor.post(f"/asks/{ask.id}/answer", json={"how": "describe", "text": " "})
    assert empty.status_code == 422
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "describe", "name": "Dana",
                                                     "text": "late 40s, tired, warm"})  # fmt: skip
    assert r.status_code == 200, r.text
    answer = r.json()["answer"]
    assert (answer["how"], answer["name"], answer["text"], answer["uses"]) == (
        "describe", "Dana", "late 40s, tired, warm", "Graceful Lady")  # fmt: skip
    db.expire_all()
    project = db.get(Project, pid)
    voice = db.query(Voice).filter_by(brand_id=project.brand_id, kind="described").one()
    assert project.voice == answer["option"] == f"voice:{voice.id}"  # the video's voice
    assert saved_voices.picked(db, project) == f"voice:{voice.id}"
    assert db.query(Job).count() == jobs  # nothing made, nothing charged
    other = _ask(db, pid, {"kind": "voice", "subject": "Mia", "question": "Mia's voice?"})
    offered = {o["id"]: o for o in _card(editor, other)["saved"]}
    assert offered[f"voice:{voice.id}"]["name"] == "Dana"  # usable wherever voices are picked
    assert offered[f"voice:{voice.id}"]["sample_url"].endswith("English_Graceful_Lady.mp3")
    same = {"how": "describe", "text": "Late 40s, tired, warm"}
    again = editor.post(f"/asks/{other.id}/answer", json=same)
    assert again.json()["answer"]["option"] == f"voice:{voice.id}"  # the same words: reused
    assert db.query(Voice).filter_by(kind="described").count() == 1


def test_a_product_shot_answer_picks_that_product_for_the_video(app, db, owner, editor):
    from app.models.brands import BrandScreen

    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    bag = product(db, project.brand_id, "bag")  # #1326: a picture's product is a library item
    db.commit()
    for variant in ("Chicken", "Peanut butter"):
        db.add(BrandScreen(brand_id=project.brand_id, name=f"Bag {variant}", product_id=bag,
                           variant=variant, file_id=upload(owner)))  # fmt: skip
    db.commit()
    ask = _ask(db, pid, {"kind": "product", "question": "Is this the bag to show at the end?"})
    card = _card(editor, ask)
    shot = next(o for o in card["saved"] if o["name"] == "Peanut butter")
    assert shot["note"] == "still" and "generate" not in card["can"]
    editor.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": shot["id"]})
    db.expire_all()
    assert db.get(Project, pid).product_variants == {"bag": "Peanut butter"}  # set, free


def test_planning_before_make_it_has_an_allowance_that_a_restart_never_resets(
    app, db, owner, editor, monkeypatch
):
    """Reed, 4 Nov: before Make it, a plan and up to 2 changes, at most 10 credits a video,
    whichever comes first, charged as they cost. Past it, a further plan change waits for the
    owner's OK on a card. Stopping and starting again, or reading the video, never resets it."""
    from decimal import Decimal

    from app.settings import get_settings

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db, ticks=4, start=False)
    plans, used, _ = asks.planned(db, project)
    assert plans >= 1 and 0 < used <= Decimal(str(get_settings().plan_credits_before_ok))
    db.rollback()  # the worker reads in this session: end the read before the note lands
    editor.post(f"{url}/messages", json={"text": "End on the capsule."})  # Change the plan
    _run(app, db, ticks=6, start=False)
    editor.get(url)  # a refresh
    (card,) = [c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "plan"]
    assert card["state"] == "open" and card["can"] == ["approve", "keep"]
    assert card["question"].startswith("Change the plan again for up to $")
    seen = editor.get(f"/projects/{pid}/asks").json()
    assert next(c for c in seen if c["kind"] == "plan")["can"] == ["withdraw"]  # Ed asked
    assert asks.planned(db, project)[1] <= Decimal(10)  # never past it without the OK

    editor.post(f"{url}/stop")  # a resend: stop, then start again
    editor.post(url)
    _run(app, db, ticks=4, start=False)
    db.expire_all()
    held = [c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "plan"]
    assert held[-1]["state"] == "open"  # the new run's plan waits for the owner too
    assert asks.planned(db, project)[1] <= Decimal(10)
    r = owner.post(f"/asks/{held[-1]['id']}/answer", json={"how": "approve"})
    assert r.json()["state"] == "answered"
    _run(app, db, ticks=6, start=False)
    kinds = [c["kind"] for c in owner.get(f"/projects/{pid}/asks").json() if c["state"] == "open"]
    assert kinds[-1] == "start"  # the OK let one more plan through: its start card is back


def _priced_down(db, pid, price: str) -> None:
    """As if Make it had approved only `price` credits: the run soon reaches it."""
    from app.credits import COUNTED

    card = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean(),
                                Job.status.in_(COUNTED)).one()  # fmt: skip
    card.input = {**card.input, "price": price}
    db.commit()


def test_past_the_price_make_it_approved_every_run_waits_for_the_owner(
    app, db, owner, editor, monkeypatch
):
    """Rule 34 and Reed, 4 Nov: nothing past the approved price runs without another OK, the
    owner's own run too; the card is S3-06's, and nothing is charged while it waits."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    for who in (owner, editor):
        pid, _ = _video(app, owner, editor, db)
        who.post(f"/projects/{pid}/director")
        _run(app, db, ticks=4, start=False)
        card = next(c for c in who.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
        assert who.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
        _priced_down(db, pid, "12")
        _run(app, db, ticks=30, start=False)
        held = [c for c in owner.get(f"/projects/{pid}/asks").json()
                if c["kind"] == "budget" and c["state"] == "open"]  # fmt: skip
        assert held and held[0]["can"] == ["approve", "keep"], who  # the owner's OK first
        assert held[0]["money"]["budget"]["credits"] == 12  # the price Make it approved
        mine = next(c for c in who.get(f"/projects/{pid}/asks").json() if c["id"] == held[0]["id"])
        assert mine["can"] == (["approve", "keep"] if who is owner else ["withdraw"])
        db.expire_all()
        waiting = db.query(Job).filter(Job.project_id == pid, Job.status == "needs_owner_approval")
        assert waiting.count() and all(j.input.get(asks.PAST_PRICE) for j in waiting)
        r = owner.post(f"/asks/{held[0]['id']}/answer", json={"how": "approve"})
        assert r.json()["state"] == "answered"


def test_a_withdraw_takes_back_only_your_own_and_others_cannot_answer(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    mine = editor.post(f"/projects/{pid}/plan").json()  # Ed's press past the budget: held
    other = Job(
        workspace_id=project.workspace_id,
        kind="image",
        provider="fake",
        project_id=pid,
        input={"held": "Waiting for the owner's OK: this goes past the video's budget."},
        credits=2,
        status="needs_owner_approval",
        created_by_id=project.created_by_id + 99,
    )
    db.add(other)
    db.flush()
    asks.held(db, other)  # someone else's press joins the same card
    db.commit()
    (card,) = editor.get(f"/projects/{pid}/asks").json()
    assert card["can"] == ["withdraw"]
    assert editor.post(f"/asks/{card['id']}/answer", json={"how": "approve"}).status_code == 403
    assert editor.post(f"/asks/{card['id']}/answer", json={"how": "keep"}).status_code == 403
    r = editor.post(f"/asks/{card['id']}/answer", json={"how": "withdraw"})
    assert r.json()["state"] == "open"  # the other press still waits
    db.expire_all()
    assert db.get(Job, mine["id"]).status == JobStatus.cancelled
    assert db.get(Job, other.id).status == JobStatus.needs_owner_approval


def test_a_parked_run_reads_an_answer_given_while_its_turn_was_asked(app, db, owner, editor):
    """QA on #1313: an answer that lands during the turn that then waits is read at once."""
    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    _ask(db, pid, QUESTION)
    second = _ask(db, pid, {**QUESTION, "question": "And the ending?", "topic": "Ending"})
    run = {"id": "r1", "turn": 1, "redos": {}, "by": project.created_by_id}
    began = utcnow()
    turn = Job(
        workspace_id=project.workspace_id,
        kind="write-claude",
        provider="claude",
        project_id=pid,
        status="succeeded",
        started_at=began,
        finished_at=began,
        input={"step": director.STEP, director.RUN: run, "result": director.ON_YOU},
    )
    db.add(turn)
    db.commit()
    assert director._parked(db, project, turn)  # nothing answered since it began
    second.state, second.answered_at = "answered", began + timedelta(milliseconds=1)
    second.answer = {"how": "reply", "text": "Toast."}
    turn.finished_at = began + timedelta(seconds=5)  # recorded after the answer landed
    db.commit()
    assert not director._parked(db, project, turn)  # it wakes to read it


def test_a_decided_question_is_never_asked_again(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {**QUESTION, "subject": "audience"})
    editor.post(f"/asks/{ask.id}/answer", json={"how": "reply", "text": "Men 30-50."})
    db.expire_all()
    said = asks.asked(db, db.get(Project, pid), None, {**QUESTION, "question": "Who's it for?",
                                                       "subject": "audience"})  # fmt: skip
    assert said == f"Refused: that's decided already (question {ask.id}: Men 30-50.)."


def test_a_role_locked_in_the_video_is_never_asked_about_or_changed(app, db, owner, editor):
    """The Cast tab's Lock (#1324: locks["roles"] as "slot:N"): never asked, never changed."""
    pid, kid = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    nate = db.query(ScriptCastSlot).filter_by(role="Nate").one()
    move = {"kind": "cast", "subject": "Nate", "question": "Who plays Nate?"}
    ask = _ask(db, pid, move)  # asked while it was open
    project.locks = {**(project.locks or {}), "roles": [f"slot:{nate.id}"]}
    db.commit()
    assert asks.asked(db, project, None, {**move, "question": "Who plays Nate now?"}) == (
        "Refused: Nate is locked in this video; use that look.")  # fmt: skip
    r = editor.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": f"item:{kid}"})
    assert r.status_code == 409 and "locked in this video" in r.json()["detail"]
    db.expire_all()
    assert str(nate.id) not in db.get(Project, pid).slot_cast  # never changed


def test_keep_on_a_plan_card_brings_back_make_it_for_the_plan_it_has(
    app, db, owner, editor, monkeypatch
):
    """QA pass 2: Keep it as it is on a planning card past the allowance is not a dead end."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db, ticks=4, start=False)
    editor.post(f"{url}/messages", json={"text": "End on the capsule."})
    _run(app, db, ticks=6, start=False)
    (card,) = [c for c in owner.get(f"/projects/{pid}/asks").json()
               if c["kind"] == "plan" and c["state"] == "open"]  # fmt: skip
    r = owner.post(f"/asks/{card['id']}/answer", json={"how": "keep"})
    assert r.json()["state"] == "answered"
    _run(app, db, ticks=4, start=False)
    cards = owner.get(f"/projects/{pid}/asks").json()
    assert [c["kind"] for c in cards if c["state"] == "open"] == ["start"]  # Make it is back
    assert editor.get(url).json()["status"] == "running"


def test_a_whole_cast_lock_also_keeps_cast_answers_out(app, db, owner, editor):
    pid, kid = _video(app, owner, editor, db)
    editor.put(f"/projects/{pid}/locks", json={"locks": {"cast": True}})
    db.expire_all()
    said = asks.asked(db, db.get(Project, pid), None,
                      {"kind": "cast", "subject": "Nate", "question": "Who plays Nate?"},
                      )  # fmt: skip
    assert said == "Refused: Nate is locked in this video; use that look."


def test_the_progress_card_reads_ready_for_its_editor_and_ignores_an_options_hold(
    app, db, owner, editor, monkeypatch
):
    """QA on f4ac1a6a: the start card is the editor's own press ("Ready to make"); a question
    card's options waiting for the owner don't make the whole run read as waiting."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    editor.post(url)
    _run(app, db, ticks=4, start=False)
    mine = editor.get(f"{url}/progress").json()
    assert (mine["title"], mine["sub"]) == ("Ready to make", "No generation started: press Make it")
    for who in (editor, owner):  # the chat's line for the run says the same to each of them
        (line,) = [m for m in who.get(url).json()["thread"] if m.get("run")]
        assert line["text"] == "Ready to make · No generation started: press Make it"
    assert owner.get(f"{url}/progress").json()["title"] == "Ready to make"  # the owner's too
    make_it(db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", project_id=pid,
               input={"ask_id": 1, "held": "Waiting for the owner's OK."}, credits=1,
               status="needs_owner_approval"))  # fmt: skip
    db.commit()
    assert editor.get(f"{url}/progress").json()["status"] != "waiting"


def test_a_cards_clone_is_saved_to_the_brands_voices_and_reused_never_charged_again(
    app, db, owner, editor
):
    """Reed, 5 Nov: "Clone it once" saves the voice to the brand's voices, said before the
    press; the same sample or the same name in that brand is the clone already made: no new
    call, nothing charged."""
    import subprocess

    from app.models.brands import Brand
    from app.models.voices import Voice

    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    brand = db.get(Brand, db.get(Project, pid).brand_id)
    assert _card(owner, ask)["clone_to"] == f"Saved to {brand.name}'s voices"
    path = f"{app.state.settings.storage_dir}/sample.mp3"
    made = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=12", path]
    subprocess.run(made, check=True)  # noqa: S603, S607 - fixed arguments
    with open(path, "rb") as f:
        data = f.read()
    first = upload(owner, "nate.mp3", data, "audio/mpeg")
    r = owner.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": first,
                                                     "text": "Nate"})  # fmt: skip
    assert r.status_code == 200, r.text
    db.expire_all()
    (voice,) = db.query(Voice).filter_by(brand_id=brand.id, kind="cloned").all()  # the brand's
    voice.provider_voice_id = "R8_NATE"  # the clone came back (the stand-in's place)
    db.commit()
    url = f"/brands/{brand.id}/voices/clone"  # the Library's Clone: the same rule
    same_bytes = upload(owner, "nate copy.mp3", data, "audio/mpeg")
    for body in ({"sample_file_id": same_bytes, "name": "Someone"},
                 {"sample_file_id": first, "name": "Nate"}):  # fmt: skip
        r = owner.post(url, json={**body, "description": ""})
        assert r.status_code in (200, 201) and r.json()["id"] == voice.id, r.text
    other = upload(owner, "other.mp3", data[:-200] + b"\0" * 200, "audio/mpeg")
    r = owner.post(url, json={"sample_file_id": other, "name": "nate", "description": ""})
    assert r.json()["id"] == voice.id  # the same name in the brand, any case
    again = owner.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": same_bytes,
                                                         "text": "Nate"})  # fmt: skip
    assert again.json()["answer"]["reused"] is True
    db.expire_all()
    assert db.query(Job).filter(Job.kind == "voice").count() == 1  # one paid call in all


def one_figure(owner, editor, pid: int) -> float:
    """The header, the run card and the newest note say one spent and one "up to", the whole
    video's (board S3-12), to the owner in dollars and to an editor in credits; the "up to" is
    never below what was spent. Returns the "up to" in credits."""
    for who in (owner, editor):
        head = who.get(f"/projects/{pid}/idea").json()
        card = who.get(f"/projects/{pid}/director/progress").json()
        notes = [t["note"] for t in who.get(f"/projects/{pid}/director").json()["thread"]
                 if t.get("note")]  # fmt: skip
        spent, top = head["spent"], head["up_to"]
        note = (
            notes[-1]
            if notes
            else {"spent": card["spent"], "up_to": card["up_to"], "spent_usd": card["spent_usd"]}
        )  # before a delivery
        assert abs(spent["credits"] - card["spent"]) < 0.001 > abs(spent["credits"] - note["spent"])
        assert top["credits"] == card["up_to"] == note["up_to"] >= note["spent"], (top, card, note)
        assert spent["usd"] == card["spent_usd"] == note["spent_usd"]
        if not notes:
            continue
        if spent["usd"] is not None:
            assert note["cost"] == f"${spent['usd']:.2f} spent of up to ${top['usd']:.2f}"
        else:
            assert note["cost"].startswith(f"{round(note['spent'])} credits used of up to ")
    return top["credits"]


def _up(credits) -> float:
    """Credits as the header rounds an "up to" (to the thousandth, up)."""
    from decimal import Decimal

    from app.ideas import _up

    return float(_up(Decimal(str(credits))))


def _start(app, db, who, pid: int) -> Job:
    """The video's run asked for: its plan, then its start card waiting for Make it."""
    who.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4, start=False)
    db.expire_all()
    return db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean(),
                                Job.status == "needs_owner_approval").one()  # fmt: skip


def _make_it(app, db, who, pid: int):
    """Make it (again) on the video's start card; the run delivers. Returns its price."""
    from decimal import Decimal

    card = next(c for c in who.get(f"/projects/{pid}/asks").json()
                if c["kind"] == "start" and c["state"] == "open")  # fmt: skip
    price = Decimal(_start_job(db, pid).input["price"])
    assert who.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    _run(app, db, ticks=40, start=False)
    return price


def _start_job(db, pid: int) -> Job:
    db.expire_all()
    return db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean()) \
        .order_by(Job.id.desc()).first()  # fmt: skip


def _spent(owner, pid: int):
    from decimal import Decimal

    return Decimal(str(owner.get(f"/projects/{pid}/idea").json()["spent"]["credits"]))


def test_the_header_the_run_card_and_the_note_say_one_figure_on_every_run(
    app, db, owner, editor, monkeypatch
):
    """QA on #1355 (boards S3-02, S3-09, S3-12): one spent and one "up to", the whole video's.
    While the start card waits, the header says its price; after the first run, the price its
    Make it approved, its planning included (not the budget beside the director's limit, QA on
    #1354); after Make it again, both prices."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(7)))  # far apart
    pid, _ = _video(app, owner, editor, db)
    card = _start(app, db, owner, pid)
    head = owner.get(f"/projects/{pid}/idea").json()
    assert head["spent"]["credits"] > 0  # its planning
    assert head["up_to"]["credits"] == _up(card.input["price"])  # the start card's figure
    first = _make_it(app, db, owner, pid)
    assert one_figure(owner, editor, pid) == _up(first)  # its look's check is the run's too
    _charge(db, pid, 3, {"auto_made": True})  # a person's own Make missing looks after it
    head = owner.get(f"/projects/{pid}/idea").json()
    assert head["up_to"]["credits"] == _up(first + 3)  # outside the run: not against its price
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 warmer."})
    _start(app, db, owner, pid)
    second = _make_it(app, db, owner, pid)
    assert one_figure(owner, editor, pid) == _up(first + second)  # every Make it, not the last


def test_after_an_ok_past_the_price_the_up_to_is_what_the_run_can_still_charge(
    app, db, owner, editor, monkeypatch
):
    """QA on #1355: the owner's OK past the price Make it approved (S3-07) lets the run spend
    more than it; the "up to" is what was spent plus what is left of the price (the steps
    past it are covered by their own OKs), never below what was spent."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    _start(app, db, owner, pid)
    card = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    _priced_down(db, pid, "12")
    url = f"/projects/{pid}/director/progress"
    for _ in range(40):  # every OK past the price, until it delivers
        if owner.get(url).json()["status"] == "delivered":
            break
        _run(app, db, ticks=10, start=False)
        for held in [c for c in owner.get(f"/projects/{pid}/asks").json()
                     if c["kind"] == "budget" and c["state"] == "open"]:  # fmt: skip
            owner.post(f"/asks/{held['id']}/answer", json={"how": "approve"})
    db.expire_all()
    price, against = asks.approved_run(db, db.get(Project, pid))
    spent = _spent(owner, pid)
    assert spent > price and against <= price  # past its price, on the owner's OKs
    assert one_figure(owner, editor, pid) == _up(spent + price - against)


def _charge(db, pid: int, credits: int, data: dict | None = None) -> None:
    """A charge on the video outside a run: a press someone made, already charged."""
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input=data or {},
               project_id=pid, credits=credits, status="succeeded"))  # fmt: skip
    db.commit()


def test_the_up_to_covers_a_charge_before_the_run_and_a_press_between_runs(app, db, owner, editor):
    """QA on #1355: the "up to" is never below what the video can still charge. A charge
    before Make it, or a press between runs, is spent outside the run; the run's whole price
    can still be charged on top of it, from the moment its start card asks."""
    from decimal import Decimal

    pid, _ = _video(app, owner, editor, db)
    _charge(db, pid, 7)
    card = _start(app, db, owner, pid)
    assert one_figure(owner, editor, pid) == _up(7 + Decimal(card.input["price"]))  # it waits
    first = _make_it(app, db, owner, pid)
    assert one_figure(owner, editor, pid) == _up(7 + first)  # the 7 before it, then its price
    _charge(db, pid, 90)  # a big press between runs: past what the first price covered
    before = _spent(owner, pid)
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 warmer."})
    _start(app, db, owner, pid)
    second = _make_it(app, db, owner, pid)
    assert before + second > first + second  # what it can reach, not every price alone
    assert one_figure(owner, editor, pid) == _up(before + second)


def _sample(app, client, name="nate.mp3") -> int:
    """A 12 s voice sample (ffmpeg's tone, free), uploaded by `client`."""
    import subprocess

    path = f"{app.state.settings.storage_dir}/sample.mp3"
    made = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=12", path]
    subprocess.run(made, check=True)  # noqa: S603, S607 - fixed arguments
    with open(path, "rb") as f:
        return upload(client, name, f.read(), "audio/mpeg")


def _clone(client, ask: Ask, sample: int, name="Nate") -> dict:
    r = client.post(f"/asks/{ask.id}/answer", json={"how": "clone", "file_id": sample,
                                                     "text": name})  # fmt: skip
    assert r.status_code == 200, r.text
    return r.json()


def test_an_editors_held_clone_is_withdrawn_and_the_card_opens_again(app, db, owner, editor):
    """Rule 22: an editor's clone waiting for the owner's OK can be withdrawn on the card
    (`can` has "cancel" while it's held): its job is cancelled, nothing is charged, the voice
    it would have made is removed, the video's voice is the one picked before (QA on #1353)
    and the card is open to answer again."""
    from app.models.jobs import Usage
    from app.models.voices import Voice

    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    editor.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": "stock:Roger"})
    sample = _sample(app, editor)
    r = _clone(editor, ask, sample)
    assert r["state"] == "held" and "cancel" in r["can"]
    db.expire_all()
    assert db.get(Project, pid).voice == r["answer"]["option"]  # the answer's voice, while held
    out = editor.post(f"/asks/{ask.id}/cancel")
    assert out.status_code == 200, out.text
    card = out.json()
    assert (card["state"], card["answer"]) == ("open", None) and "clone" in card["can"]
    db.expire_all()
    job = db.query(Job).filter(Job.kind == "voice").one()
    assert job.status == JobStatus.cancelled
    assert not db.query(Usage).filter_by(job_id=job.id).count()  # nothing charged
    assert db.query(Voice).filter_by(name="Nate", kind="cloned").one().archived_at is not None
    video = db.get(Project, pid)
    assert video.voice == "stock:Roger"  # the earlier pick, still the person's
    assert [e["now"] for e in video.settings_log if e["field"] == "voice"][-1] == "stock:Roger"
    again = _clone(editor, ask, sample)
    assert again["state"] == "held"  # asked again
    db.expire_all()
    started = db.query(Job).filter(Job.kind == "voice").order_by(Job.id.desc()).first()
    started.status = JobStatus.running
    db.commit()
    late = editor.post(f"/asks/{ask.id}/cancel")
    assert late.status_code == 409 and "started or ended" in late.json()["detail"]


def test_the_owner_withdraws_an_editors_held_clone(app, db, owner, editor, monkeypatch):
    """The owner may withdraw any held clone; the director hears the card is open again."""
    woken = []
    monkeypatch.setattr(director, "wake", lambda db, project: woken.append(project.id))
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    _clone(editor, ask, _sample(app, editor))
    woken.clear()
    out = owner.post(f"/asks/{ask.id}/cancel").json()
    assert out["state"] == "open" and woken == [pid]
    db.expire_all()
    assert db.query(Job).filter(Job.kind == "voice").one().status == JobStatus.cancelled
    assert db.get(Project, pid).voice is None  # nothing was picked before


def test_a_card_that_reused_someone_elses_clone_opens_again_and_its_voice_goes_back(
    app, db, owner, editor
):
    """QA on #1353: a card that reused a clone still being made (the owner's, from the
    Library) opens again on Withdraw, the owner's clone goes on, and the video is not left
    narrated in the withdrawn voice."""
    pid, _ = _video(app, owner, editor, db)
    brand = db.get(Project, pid).brand_id
    sample = _sample(app, owner)
    body = {"sample_file_id": sample, "name": "Nate", "description": ""}
    r = owner.post(f"/brands/{brand}/voices/clone", json=body)
    assert r.status_code in (200, 201), r.text
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    editor.post(f"/asks/{ask.id}/answer", json={"how": "saved", "option": "stock:Roger"})
    mine = _clone(editor, ask, _sample(app, editor, "copy.mp3"))  # the same bytes: reused
    assert mine["answer"]["option"] == f"voice:{r.json()['id']}"
    db.expire_all()
    assert db.query(Job).filter(Job.kind == "voice").count() == 1  # no second clone
    out = editor.post(f"/asks/{ask.id}/cancel")
    assert out.status_code == 200 and out.json()["state"] == "open", out.text
    db.expire_all()
    assert db.query(Job).filter(Job.kind == "voice").one().status == JobStatus.queued  # goes on
    assert db.get(Project, pid).voice == "stock:Roger"


def test_withdrawing_a_clone_another_card_reused_says_so_on_that_card(app, db, owner, editor):
    """QA on #1353: when the editor withdraws their clone, a card that reused it says the
    clone was withdrawn (not that it failed) and can be answered again."""
    pid, _ = _video(app, owner, editor, db)
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    _clone(editor, ask, _sample(app, editor))
    other = _ask(db, pid, {"kind": "voice", "subject": "Mom", "question": "And Mom's voice?"})
    reused = _clone(owner, other, _sample(app, owner, "copy.mp3"))
    assert reused["answer"]["option"] == _card(editor, ask)["answer"]["option"]
    assert editor.post(f"/asks/{ask.id}/cancel").status_code == 200
    card = _card(owner, other)
    assert card["state"] == "failed" and card["answer"]["withdrawn"] is True
    assert "clone" in card["can"]  # answerable again
    db.expire_all()
    assert db.get(Project, pid).voice is None


def test_withdrawing_a_clone_of_a_brand_voice_never_removes_that_voice(app, db, owner, editor):
    """QA on #1353: a failed voice in the brand's Library cloned again in its own row (the
    same name) is put back as it was on Withdraw, never removed, nor its character's voice."""
    from app.models.voices import Voice

    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    first = _sample(app, owner, "first.mp3")
    nate = Voice(workspace_id=project.workspace_id, brand_id=project.brand_id, name="Nate",
                 kind="cloned", provider="minimax", speech_model=saved_voices.SPEAKS,
                 description="", sample_file_id=first,
                 created_by_id=project.created_by_id)  # fmt: skip
    db.add(nate)
    db.commit()
    assert saved_voices.state(db, nate)[0] == "failed"
    ask = _ask(db, pid, {"kind": "voice", "subject": "Nate", "question": "Which voice?"})
    r = _clone(editor, ask, _sample(app, editor, "other.mp3"))  # by name: Nate's row, again
    assert r["answer"]["option"] == f"voice:{nate.id}" and r["state"] == "held"
    assert editor.post(f"/asks/{ask.id}/cancel").status_code == 200
    db.expire_all()
    nate = db.get(Voice, nate.id)
    assert nate.archived_at is None and nate.sample_file_id == first and nate.job_id is None


def test_a_revision_never_says_no_generation_started(app, db, owner, editor):
    """QA on the cut screens (board S3-12, "Working · revising · $9.84 spent"): once a run has
    made the video, the header never says "No generation started" again, while a revision
    plans or waits on its own Make it; before the first Make it, it does (S3-02). A revision's
    waiting start card says the delivered cut stays as it is until it's pressed, or, held for
    the owner, until the owner says yes."""
    pid, _ = _video(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    _start(app, db, owner, pid)
    assert owner.get(url).json()["started"] is False  # the first start card waits
    first = owner.get(f"{url}/progress").json()
    assert first["title"] == "Ready to make"
    assert first["sub"] == "No generation started: press Make it"
    _make_it(app, db, owner, pid)
    assert owner.get(url).json()["started"] is True
    cut = [t["note"]["cut"] for t in owner.get(url).json()["thread"] if t.get("note")][-1]
    owner.post(f"{url}/messages", json={"text": "Make clip 1 warmer."})
    editor.post(url)  # Make it again, the editor's: the revision plans first
    assert owner.get(f"{url}/progress").json()["status"] == "revising"
    assert owner.get(url).json()["started"] is True
    _run(app, db, ticks=4, start=False)  # its start card waits, past the budget: the owner's
    mine = owner.get(f"{url}/progress").json()
    assert mine["title"] == "Ready to make"
    assert mine["sub"] == f"Cut {cut} stays as it is until you press Make it"
    theirs = editor.get(f"{url}/progress").json()
    assert theirs["title"] == "Waiting for the owner's OK"
    assert theirs["sub"] == f"Cut {cut} stays as it is until the owner says yes"
    assert owner.get(url).json()["started"] is True and editor.get(url).json()["started"] is True


def test_notes_kept_before_their_parts_existed_still_show(app, db, owner, editor):
    """QA on the test site's videos: a delivery's note kept as plain words, or as a dict from
    before the cut was numbered, shows as it is (never a 500); a revision's start card then says
    "The cut stays as it is", with no number."""
    pid, _ = _video(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    _start(app, db, owner, pid)
    _make_it(app, db, owner, pid)
    delivered = next(j for j in director.turns(db, db.get(Project, pid))
                     if j.input.get("result") == "Delivered.")  # fmt: skip
    for old, cut in (({"made": "The cut.", "spent": 9, "up_to": 20}, None),
                     ("Here's the cut. Nothing else.", None)):  # fmt: skip
        delivered.output = {**delivered.output, "note": old}
        db.commit()
        for who in (owner, editor):
            r = who.get(url)
            assert r.status_code == 200, r.text
            (line,) = [t for t in r.json()["thread"] if t["id"] == f"t{delivered.id}"]
            if isinstance(old, str):
                assert line["note"] is None and line["text"] == old  # its words, as they were
            else:
                assert line["note"]["cut"] is cut and line["note"]["made"] == "The cut."
                assert line["note"]["redid"] == [] and "The cut." in line["text"]
    owner.post(f"{url}/messages", json={"text": "Make clip 1 warmer."})
    editor.post(url)  # Make it again, the editor's: held for the owner
    _run(app, db, ticks=4, start=False)
    mine, theirs = owner.get(f"{url}/progress").json(), editor.get(f"{url}/progress").json()
    assert mine["sub"] == "The cut stays as it is until you press Make it"
    assert theirs["sub"] == "The cut stays as it is until the owner says yes"


def test_a_video_delivered_before_start_cards_never_reads_no_generation_started(
    app, db, owner, editor
):
    """QA on the cut screens: a video the test site delivered before start cards existed (its
    turns carry no `ok`, it has no start card) says what was spent while a new run plans or its
    cut is remade, never "No generation started" (S3-12)."""
    pid, _ = _video(app, owner, editor, db)
    _start(app, db, owner, pid)
    _make_it(app, db, owner, pid)
    for j in db.query(Job).filter(Job.project_id == pid):  # as it was before start cards
        data = {k: v for k, v in j.input.items() if k not in (asks.START, "price")}
        if isinstance(data.get(director.RUN), dict):
            data[director.RUN] = {k: v for k, v in data[director.RUN].items() if k != "ok"}
        j.input = data
    db.commit()
    url = f"/projects/{pid}/director"
    owner.post(f"{url}/messages", json={"text": "Make clip 1 warmer."})
    owner.post(url)  # a new run: planning before its own Make it
    assert owner.get(url).json()["started"] is True
    assert editor.get(url).json()["started"] is True


def test_a_start_card_after_a_stopped_run_says_nothing_more_is_made(app, db, owner, editor):
    """QA on #1367: Make it, Stop, then Make it again: generation has started (the header shows
    what was spent), so the new start card never says "No generation started"; with no cut
    delivered it says nothing more is made until it's pressed, or until the owner says yes."""
    pid, _ = _video(app, owner, editor, db)
    url = f"/projects/{pid}/director"
    _start(app, db, owner, pid)
    card = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    _run(app, db, ticks=6, start=False)  # it generates for a while
    assert owner.post(f"{url}/stop").status_code == 200
    assert owner.get(f"/projects/{pid}/idea").json()["spent"]["credits"] > 0
    editor.post(url)  # Make it again, the editor's: its card waits for the owner
    _run(app, db, ticks=4, start=False)
    mine, theirs = owner.get(f"{url}/progress").json(), editor.get(f"{url}/progress").json()
    assert (mine["title"], mine["sub"]) == (
        "Ready to make", "Nothing more is made until you press Make it")  # fmt: skip
    assert (theirs["title"], theirs["sub"]) == (
        "Waiting for the owner's OK", "Nothing more is made until the owner says yes")  # fmt: skip
    assert owner.get(url).json()["started"] is True and editor.get(url).json()["started"] is True


def _past_price(app, db, owner, pid: int, price: str) -> dict:
    """The newest run's Make it as if it had approved only `price` credits; the run goes on
    until a step past it waits for the owner. Its budget card, as the owner reads it."""
    from app.credits import COUNTED

    cards = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean(),
                                 Job.status.in_(COUNTED))  # fmt: skip
    newest = cards.order_by(Job.id.desc()).first()
    newest.input = {**newest.input, "price": price}
    db.commit()
    for _ in range(20):
        _run(app, db, ticks=10, start=False)
        cards = [c for c in owner.get(f"/projects/{pid}/asks").json()
                 if c["kind"] == "budget" and c["state"] == "open"]  # fmt: skip
        if cards:
            return cards[-1]
    raise AssertionError("no step went past the price")


def _said(money: dict, owner: bool) -> str:
    return f"${money['usd']:.2f}" if owner else f"{math.ceil(money['credits'])} credits"


def test_past_the_first_runs_price_the_card_says_the_boards_words_in_its_figures(
    app, db, owner, editor, monkeypatch
):
    """Rule 34 (Reed, 6 Nov) and board S3-07: a first run past the price its Make it approved
    says "past the budget" and "takes this video to up to … its budget is …", the figures
    being the run's own (the hold's: asks.approved_run); an editor reads credits."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    _start(app, db, editor, pid)
    first = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
    owner.post(f"/asks/{first['id']}/answer", json={"how": "make_it"})
    card = _past_price(app, db, owner, pid, "12")
    m = card["money"]
    db.expire_all()
    price, against = asks.approved_run(db, db.get(Project, pid))
    assert m["budget"]["credits"] == float(price)  # the hold's own figures
    assert abs(m["spent"]["credits"] - float(against)) < 1
    past = _said(m["past"], True)
    assert card["question"] == f"{m['what']}? That goes {past} past the budget."
    total = round(m["spent"]["usd"] + m["up_to"]["usd"], 2)
    assert m["past"]["usd"] > 0 and m["past"]["usd"] == round(total - m["budget"]["usd"], 2)
    waiting = db.query(Job).filter(Job.project_id == pid, Job.status == "needs_owner_approval")
    judged = sum(Decimal(j.input[asks.HELD_CREDITS]) for j in waiting)  # what the hold judged
    assert judged > 0 and m["up_to"]["credits"] >= float(judged)  # Approve covers all of it
    assert card["why"].endswith(
        f"takes this video to up to ${total:.2f} ({_said(m['spent'], True)} spent plus up to "
        f"{_said(m['up_to'], True)}); its budget is {_said(m['budget'], True)}."
    )  # fmt: skip
    assert m["over"] == "the budget" and card["can"] == ["approve", "keep"]
    theirs = next(c for c in editor.get(f"/projects/{pid}/asks").json() if c["id"] == card["id"])
    t = theirs["money"]
    sums = t["spent"]["credits"] + t["up_to"]["credits"] - t["budget"]["credits"]
    assert t["past"]["credits"] > 0 and t["past"]["credits"] == sums
    past = _said(t["past"], False)
    assert theirs["question"] == f"{t['what']}? That goes {past} past the budget."
    assert theirs["why"].endswith("The owner has been asked; nothing is charged while it waits.")
    assert "$" not in theirs["question"] + theirs["why"] and theirs["can"] == ["withdraw"]


def test_past_a_later_runs_price_the_card_speaks_in_that_runs_own_figures(
    app, db, owner, editor, monkeypatch
):
    """Rule 34: after a delivery, Make it again holds the new run to its own approved price;
    its budget card says how far past that run's price it goes and what this run has spent,
    in the figures the hold uses (asks.approved_run), to the owner in dollars and an editor in
    credits."""
    from decimal import Decimal

    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(500)))
    pid, _ = _video(app, owner, editor, db)
    _start(app, db, owner, pid)
    _make_it(app, db, owner, pid)  # delivered
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 warmer."})
    _start(app, db, owner, pid)
    second = [c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start"][-1]
    owner.post(f"/asks/{second['id']}/answer", json={"how": "make_it"})
    card = _past_price(app, db, owner, pid, "3")
    m = card["money"]
    db.expire_all()
    price, against = asks.approved_run(db, db.get(Project, pid))
    assert m["budget"]["credits"] == float(price)  # the hold's own figures
    assert abs(m["spent"]["credits"] - float(against)) < 1
    p = _said(m["budget"], True)
    assert m["over"] == f"the {p} approved for this run"
    assert card["question"] == (
        f"{m['what']}? That goes {_said(m['past'], True)} past the {p} approved for this run."
    )
    total = round(m["spent"]["usd"] + m["up_to"]["usd"], 2)
    assert m["past"]["usd"] > 0 and m["past"]["usd"] == round(total - m["budget"]["usd"], 2)
    assert card["why"].endswith(
        f"takes this run to up to ${total:.2f} ({_said(m['spent'], True)} spent in this run plus "
        f"up to {_said(m['up_to'], True)}); this run's approved price is {p}."
    )  # fmt: skip
    theirs = next(c for c in editor.get(f"/projects/{pid}/asks").json() if c["id"] == card["id"])
    t = theirs["money"]
    sums = t["spent"]["credits"] + t["up_to"]["credits"] - t["budget"]["credits"]
    assert t["past"]["credits"] > 0 and t["past"]["credits"] == sums
    over = f"the {_said(t['budget'], False)} approved for this run"
    assert theirs["question"] == f"{t['what']}? That goes {_said(t['past'], False)} past {over}."
    assert "$" not in theirs["question"] + theirs["why"]


def test_a_look_past_the_videos_budget_asks_for_all_the_hold_judged(app, db, owner, editor):
    """Rule 36 (QA after #1371): an editor's own Make a look past the video's budget waits on its
    card for the whole of what the hold judged (the sheet, its check and its one redo), so the
    card's up to, how far past and Approve never understate it."""
    from decimal import Decimal

    pid, _ = _video(app, owner, editor, db)
    project = db.get(Project, pid)
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=pid, credits=project.budget_credits, status="succeeded"))  # fmt: skip
    db.commit()
    slot = next(r for r in editor.get(f"/projects/{pid}/assets").json()
                if r.get("slot_id") and not r.get("library_item_id"))["slot_id"]  # fmt: skip
    editor.post(f"/projects/{pid}/assets/slots/{slot}/make-look")
    db.expire_all()
    (sheet,) = db.query(Job).filter(Job.project_id == pid, Job.status == "needs_owner_approval")
    judged = Decimal(sheet.input[asks.HELD_CREDITS])
    assert judged > sheet.credits  # the sheet with its check and one redo
    card = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "budget")
    m = card["money"]
    assert m["up_to"]["credits"] >= float(judged) and m["over"] == "the budget"
    total = round(m["spent"]["usd"] + m["up_to"]["usd"], 2)
    assert m["past"]["usd"] > 0 and m["past"]["usd"] == round(total - m["budget"]["usd"], 2)
    assert card["question"].endswith(f"That goes {_said(m['past'], True)} past the budget.")
    assert sheet.input.get(asks.PAST_PRICE) is None  # the video's budget, not a run's price
