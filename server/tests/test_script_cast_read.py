"""Reading the cast: Claude lists the roles; existing slots stay, new ones are added."""

from app.models.jobs import Job
from app.models.script_library import Script
from app.script_cast_read import save_cast_slots
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_script_library import SCRIPT, _make
from tests.test_script_preview import _work


def test_reading_keeps_locked_slots_and_adds_new_roles(app, db, owner):
    made = _make(owner, title="Dip", description="Mom finds the wallet", text=SCRIPT)
    base = f"/scripts/{made['id']}"
    url = f"{base}/cast/read"
    assert owner.post(url).json()["detail"] == "Approve the original first."
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    owner.post(f"{base}/cast", json={"role": "Coach"})
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[1]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia.json()["id"]})
    owner.post(f"{base}/drafts/0/approve")

    job = owner.post(url)
    assert job.status_code == 201, job.text
    assert owner.post(url).status_code == 409  # one at a time
    assert owner.get(url).json() == {"running": True, "problems": []}
    prompt = db.get(Job, job.json()["id"]).input["prompt"]
    assert "<brief>Dip: Mom finds the wallet</brief>" in prompt
    assert f"char:{mia.json()['id']} Mia (Mom)" in prompt and '<version slot="0">' in prompt
    _work(app, db)
    cast = owner.get(base).json()["cast"]
    assert [(s["role"], s["locked"], s["kind"], s["appears_in"]) for s in cast] == [
        ("Mom", True, "Main", [0]),  # found and already there: kept, still locked
        ("Nate", False, "Main", [0]),  # new (recurring: Main)
        ("Coach", False, "Main", []),  # not in the script any more: kept, flagged by []
    ]
    assert cast[1]["description"] == "A practice look."
    found = owner.get(url).json()
    assert found["running"] is False
    assert all(p.startswith("Advice: ") for p in found["problems"])


def test_reading_follows_the_script_rules(owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/cast/read"
    assert editor.post(url).status_code == 404  # private until published
    owner.post(f"/scripts/{made['id']}/drafts/0/approve")
    owner.post(f"/scripts/{made['id']}/publish")
    assert editor.get(url).status_code == 200
    assert editor.post(url).status_code in (403, 409)  # published: final


def test_publish_waits_for_a_read_and_a_late_result_is_dropped(app, db, owner):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    assert owner.post(f"{base}/cast/read").status_code == 201
    assert owner.post(f"{base}/publish").status_code == 409  # still writing
    db.query(Script).filter_by(id=made["id"]).update({"published": True})
    db.commit()
    _work(app, db)
    assert owner.get(base).json()["cast"] == []


def test_a_role_listed_twice_is_one_slot(db, owner):
    """QA #239: Claude naming a role twice merges it, instead of failing after the paid call."""
    made = _make(owner, text=SCRIPT)
    script = db.get(Script, made["id"])
    row = {"description": "teen", "recurring": True, "kind": "Main"}
    job = Job(  # the finished job as the worker hands it over (not saved)
        input={"step": "cast_slots", "script_id": script.id},
        output={
            "slots": [
                {**row, "role": "Nate", "appears_in": [0]},
                {**row, "role": "nate", "appears_in": [1]},
                {**row, "role": "Nate, the teen groom", "appears_in": [2]},  # the live test
            ]
        },
    )
    save_cast_slots(db, job)
    db.commit()
    cast = owner.get(f"/scripts/{made['id']}").json()["cast"]
    # Mom speaks too, so the backstop gives her the role the read left out (Reed: FRIEND)
    assert [(s["role"], s["appears_in"]) for s in cast] == [("Nate", [0, 1, 2]), ("Mom", [0])]


def test_a_roles_facts_and_its_guesses(db, owner):
    """Reed, 2026-10-26: a role says its age range, gender and job, guesses marked; a person
    writing the description makes none of it a guess."""
    from app.routes.script_cast import role_facts

    facts = role_facts("Mid-40s woman, a primary-school teacher; curly hair", ["age"])
    assert facts.model_dump() == {
        "age_range": {"value": "Mid-40s", "inferred": True},
        "gender": {"value": "woman", "inferred": False},
        "occupation": {"value": "primary-school teacher", "inferred": False},
    }
    assert role_facts("A practice look.", []).model_dump() == {
        "age_range": None, "gender": None, "occupation": None
    }  # fmt: skip

    made = _make(owner, text=SCRIPT)
    lead = "17-year-old boy, a student; lanky"
    nate = {"role": "Nate", "appears_in": [0], "recurring": True, "kind": "Main",
            "description": lead, "guessed": ["occupation"]}  # fmt: skip
    job = Job(input={"step": "cast_slots", "script_id": made["id"]}, output={"slots": [nate]})
    save_cast_slots(db, job)
    db.commit()
    url = f"/scripts/{made['id']}"
    nate = next(c for c in owner.get(url).json()["cast"] if c["role"] == "Nate")
    assert nate["facts"]["occupation"] == {"value": "student", "inferred": True}
    assert nate["facts"]["age_range"] == {"value": "17-year-old", "inferred": False}
    owner.patch(f"{url}/cast/{nate['id']}", json={"description": "17-year-old boy, a student"})
    nate = next(c for c in owner.get(url).json()["cast"] if c["role"] == "Nate")
    assert nate["facts"]["occupation"]["inferred"] is False


def test_only_people_who_speak_get_a_role_never_script_cues(db, owner):
    """QA on #565: CUT TO:, MUSIC:, SFX:, FADE OUT: and the like are cues, not people (each
    role would auto-make a paid look); "(V.O.)" is the same speaker; a name with no words
    after it speaks nothing."""
    from app.script_cast_read import _speakers

    cues = "\n".join([
        "SCENE 1 — INT. KITCHEN — DAY", "INT. KITCHEN — DAY:", "CUT TO:", "SMASH CUT TO:",
        "MUSIC: soft piano", "SFX: a door slams", "FADE OUT:", "SUPER: Two years later",
        "TITLE: The empty chair", "TEXT ON SCREEN: $348,920", "INSERT: the phone",
        "MOM: Nate, where is all your money?", "NATE (V.O.): I bought the dip.", "FRIEND:",
    ])  # fmt: skip
    made = _make(owner, text=cues)
    assert _speakers(db, db.get(Script, made["id"])) == {"Mom": [0], "Nate": [0]}
