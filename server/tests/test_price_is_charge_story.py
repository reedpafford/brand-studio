"""Shown price = what's charged, the story steps (plan, breakdown, cast and looks, storyboard;
the Producer's sweep, as #986 did for Make this version; Builder-Server-8 has the rest): for
each paid press, read the price its screen shows, press it on the free stand-ins, let every
job the press starts run, and compare what they charged. Prices shown rounded up (whole
credits) are met when the charge rounds up to them; "up to" ones are never passed."""

from decimal import Decimal

from sqlalchemy import func, select

from app.credits import price
from app.models.jobs import Job
from app.providers import get_providers
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_fake_local import _drain


def _press(app, db, providers, press):
    """(the response, the credits every job it started charged once they all ran)."""
    before = db.scalar(select(func.max(Job.id))) or 0
    response = press()
    assert response.status_code < 300, response.text
    _drain(app, db, providers)
    db.expire_all()
    jobs = db.scalars(select(Job).where(Job.id > before)).all()
    return response, sum((Decimal(j.credits or 0) for j in jobs), Decimal(0))


def _rate(client, kind: str) -> float:
    return next(r["credits_per_unit"] for r in client.get("/credits/rates").json()
                if r["kind"] == kind)  # fmt: skip


def test_the_breakdown_and_storyboard_presses_charge_their_shown_price(app, db, editor, setup):  # noqa: F811
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    url = f"/projects/{setup['project']}"
    seen = []  # (step, press, shown, charged)

    def check(step, press, shown, call, up_to=False):
        response, charged = _press(app, db, providers, call)
        seen.append((step, press, float(shown), float(charged), up_to))
        return response

    assert editor.get(f"{url}/breakdown/price").json()["credits"] == _rate(editor, "write-claude")
    check("breakdown", "Make the shots", _rate(editor, "write-claude"),
          lambda: editor.post(f"{url}/breakdown"))  # fmt: skip
    check("storyboard", "Make the storyboard", _rate(editor, "write-claude"),
          lambda: editor.post(f"{url}/storyboard", json={"per_shot": False}))  # fmt: skip
    frame = editor.get(f"{url}/storyboard").json()[0]
    frames = editor.get(f"{url}/storyboard").json()
    many = price(Decimal(str(frame["still_exact_credits"] * len(frames))))  # "Make N stills"

    def every():
        for f in frames:
            drawn = editor.post(f"{url}/storyboard/frames/{f['id']}/render")
            assert drawn.status_code == 201, drawn.text
        return drawn

    check("storyboard", "Make every still (exact price, rounded once)", many, every)
    exact = Decimal(str(frame["still_exact_credits"]))  # 0.33 against 1 a still: 9 stills
    assert (price(9 * exact), 9 * frame["still_credits"]) == (3, 9)  # are 3, never 9
    check("storyboard", "Make still again", frame["still_credits"],
          lambda: editor.post(f"{url}/storyboard/frames/{frame['id']}/render"))  # fmt: skip
    change = editor.get(f"{url}/storyboard/frames/{frame['id']}/change").json()["credits"]
    check("storyboard", "Change it (still)", change,
          lambda: editor.post(f"{url}/storyboard/frames/{frame['id']}/change",
                              json={"note": "Make the light warmer"}))  # fmt: skip
    for f in editor.get(f"{url}/storyboard").json():
        draw = f"{url}/storyboard/frames/{f['id']}/render"
        if not f["file_id"]:
            _press(app, db, providers, lambda draw=draw: editor.post(draw))
        editor.post(f"{url}/storyboard/frames/{f['id']}/approve")
    from app.models.storyboards import StoryboardFrame

    row = db.get(StoryboardFrame, frame["id"])  # a word the image model refuses, as written
    row.prompt = f"{row.prompt} In leggings."
    db.commit()
    check("storyboard", "Soften it (free)", 0,
          lambda: editor.post(f"{url}/storyboard/frames/{frame['id']}/soften"))  # fmt: skip
    # Clip prompts (Builder-Server-8's step) as setup: Make the shots again rewrites them
    _press(app, db, providers, lambda: editor.post(f"{url}/clips/prompts"))
    check("breakdown", "Make the shots again (fixed)",
          editor.get(f"{url}/breakdown/price").json()["credits"],
          lambda: editor.post(f"{url}/breakdown"))  # fmt: skip
    frame = editor.get(f"{url}/storyboard").json()[0]
    assert frame["redo_credits"] is not None, frame
    check("storyboard", "Redo this frame", frame["redo_credits"],
          lambda: editor.post(f"{url}/storyboard/frames/{frame['id']}/redo"))  # fmt: skip
    check("storyboard", "Redo storyboard (frames again)", _rate(editor, "write-claude"),
          lambda: editor.post(f"{url}/storyboard", json={"per_shot": False}))  # fmt: skip
    _report(seen)


def test_the_plan_presses_charge_their_shown_price(app, db, editor, setup):  # noqa: F811
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    pid = setup["project"]
    url = f"/projects/{pid}/plan"
    seen = []
    shown = editor.get(f"/projects/{pid}").json()["plan_credits"]
    _, charged = _press(app, db, providers, lambda: editor.post(url, json={}))
    seen.append(("plan", "Make the plan", float(shown), float(charged), False))
    plan = editor.get(url).json()
    note = {"note": "funnier"}
    _, charged = _press(app, db, providers,
                        lambda: editor.post(f"{url}/scenes/1/change", json=note))  # fmt: skip
    seen.append(("plan", "Change this scene", float(plan["change_scene_credits"]),
                 float(charged), False))  # fmt: skip
    plan = editor.get(url).json()
    _, charged = _press(app, db, providers, lambda: editor.post(f"{url}/approve"))
    seen.append(("plan", "Approve the plan (makes the shots)", float(plan["approve_credits"]),
                 float(charged), False))  # fmt: skip
    _report(seen)


def test_the_cast_and_looks_presses_charge_their_shown_price(app, db, owner, editor):
    from tests.conftest import upload
    from tests.test_video_looks import _row
    from tests.test_video_looks import _video as nate_video

    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    seen = []
    _, pid, nate = nate_video(owner, editor, db)
    row = _row(editor, pid, nate)
    make = f"/projects/{pid}/assets/slots/{nate}/make-look"
    _, charged = _press(app, db, providers, lambda: editor.post(make))
    seen.append(("cast", "Make a look (up to)", float(row["look_credits"]), float(charged), True))
    seen.append(("cast", "Make a look (usually)", float(row["look_usual_credits"]),
                 float(charged), False))  # fmt: skip

    _, other, _ = nate_video(owner, editor, db)
    missing = editor.get(f"/projects/{other}/assets/missing-looks").json()
    _, charged = _press(app, db, providers,
                        lambda: editor.post(f"/projects/{other}/assets/make-missing"))  # fmt: skip
    seen.append(("cast", "Make the missing looks (up to)", float(missing["credits"]),
                 float(charged), True))  # fmt: skip
    seen.append(("cast", "Make the missing looks (usually)", float(missing["usual_credits"]),
                 float(charged), False))  # fmt: skip

    from tests.test_look_sheets import _video as pixar_video

    pixar, locked = pixar_video(app, owner, editor, db)
    row = next(r for r in editor.get(f"/projects/{pixar.id}/assets").json()
               if r["library_item_id"] == locked)  # fmt: skip
    copy = f"/projects/{pixar.id}/assets/looks/{locked}/copy"
    _, charged = _press(app, db, providers, lambda: editor.post(copy))
    seen.append(("cast", "Make a Disney Pixar look for this video (up to)",
                 float(row["look_credits"]), float(charged), True))  # fmt: skip
    seen.append(("cast", "Make a Disney Pixar look for this video (usually)",
                 float(row["look_usual_credits"]), float(charged), False))  # fmt: skip

    mia = owner.post("/library/character", json={"name": "Mia", "notes": "a woman of 30",
                                                 "image_file_ids": [upload(owner)]})  # fmt: skip
    item = f"/library/character/{mia.json()['id']}"
    shown = owner.get(item).json()
    _, charged = _press(app, db, providers, lambda: owner.post(f"{item}/sheet", json={}))
    seen.append(("cast", "Make sheet (up to)", float(shown["sheet_credits"]), float(charged), True))
    seen.append(("cast", "Make sheet (usually)", float(shown["sheet_usual_credits"]),
                 float(charged), False))  # fmt: skip
    shown = owner.get(item).json()
    change = {"change": "Softer light"}
    _, charged = _press(app, db, providers, lambda: owner.post(f"{item}/sheet", json=change))
    seen.append(("cast", "Change this… (sheet)", float(shown["change_credits"]), float(charged),
                 False))  # fmt: skip
    _report(seen)


def _report(seen: list) -> None:
    for row in seen:
        print("PRICE", *row)  # the PR's table (pytest -s)
    assert not [r for r in seen if not _met(*r[2:])], seen


def _met(shown: float, charged: float, up_to: bool) -> bool:
    """Never above the shown price; a fixed price is the same once both are rounded up."""
    if charged > shown + 0.005:
        return False
    return up_to or price(Decimal(str(charged))) == price(Decimal(str(shown)))
