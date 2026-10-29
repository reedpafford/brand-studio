"""The price shown is the charge (the Producer's check, split by step with Next-Server): for
each paid press of Clips, the final cut, Update everything after this, Quick clip and the
script steps, the price the screen shows is the charge, rounded up, never below it. All on
the stand-ins (no paid calls)."""

from decimal import Decimal

from app.credits import price
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_fake_local import _drain
from tests.test_song_takes import song  # noqa: F401 - fixture
from tests.test_update_after import _made


def _last(db) -> int:
    return db.query(Job.id).order_by(Job.id.desc()).limit(1).scalar() or 0


def _charged(db, since: int) -> Decimal:
    """What the jobs made since `since` charged, once they're done (a stopped one: nothing)."""
    db.expire_all()
    jobs = db.query(Job).filter(Job.id > since, Job.status != JobStatus.cancelled)
    return sum((j.credits for j in jobs), Decimal(0))


def _is_the_charge(shown: float, charged: Decimal) -> None:
    """The shown price is the charge rounded up: never below it, and less than one above."""
    assert charged > 0, "nothing was charged"
    assert price(charged) == shown, f"shown {shown}, charged {charged}"


def test_clip_presses_charge_what_they_show(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    _drain(app, db, providers)

    # Rewrite clip prompts · N (every stale clip)
    shown = editor.get(f"{url}/clips/prompts/price").json()["credits"]
    since = _last(db)
    assert editor.post(f"{url}/clips/prompts", json={}).status_code == 201
    _drain(app, db, providers)
    _is_the_charge(shown, _charged(db, since))

    # Make clip · N (one take)
    clip = editor.get(f"{url}/clips").json()[0]
    for c in editor.get(f"{url}/clips").json():
        editor.post(f"{url}/clips/{c['id']}/prompt-ok")
    since = _last(db)
    made = editor.post(f"{url}/clips/{clip['id']}/generate", json={})
    assert made.status_code == 201, made.text
    _drain(app, db, providers)
    _is_the_charge(price(Decimal(str(clip["take_credits"]))), _charged(db, since))

    # Change it · N (the prompt rewritten, then its new take)
    shown = editor.get(f"{url}/clips/{clip['id']}/change").json()["credits"]
    since = _last(db)
    changed = editor.post(f"{url}/clips/{clip['id']}/change", json={"note": "Slower push in."})
    assert changed.status_code == 201, changed.text
    _drain(app, db, providers)
    _is_the_charge(shown, _charged(db, since))


def test_free_clip_presses_charge_nothing(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    _drain(app, db, providers)
    row = db.query(ProjectClip).first()
    since = _last(db)
    editor.post(f"{url}/clips/{row.id}/fix")  # Fix this clip's prompt: free
    _drain(app, db, providers)
    editor.post(f"{url}/clips/{row.id}/auto-fix/undo")  # Undo a wording fix: free
    assert _charged(db, since) == 0


def test_update_everything_after_this_charges_what_it_shows(app, db, owner, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)  # new shots: the storyboard, stills, prompts after
    shown = editor.get(f"{url}/update-after").json()
    assert len(shown["steps"]) >= 2  # a run of several paid steps, priced once
    since = _last(db)
    assert owner.post(f"{url}/update-after").status_code == 202  # the owner presses it too
    for _ in range(4):
        _drain(app, db, providers)
    _is_the_charge(shown["credits"], _charged(db, since))


def test_the_final_cut_is_free(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    _drain(app, db, providers)
    editor.post(f"{url}/clips/prompts", json={})
    _drain(app, db, providers)
    for c in editor.get(f"{url}/clips").json():
        editor.post(f"{url}/clips/{c['id']}/prompt-ok")
        assert editor.post(f"{url}/clips/{c['id']}/generate", json={}).status_code == 201
        _drain(app, db, providers)
        assert editor.post(f"{url}/clips/{c['id']}/approve").status_code == 200
    since = _last(db)
    made = editor.post(f"{url}/video")
    assert made.status_code == 201, made.text
    assert _charged(db, since) == 0  # Make the video: no credits, no provider


def test_a_quick_clip_charges_what_its_estimate_shows(app, db, owner, editor):
    from app.providers import get_providers
    from tests.conftest import upload

    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    brand = owner.get("/brands").json()[0]["id"]
    picture = upload(editor)
    asks = [
        {"duration": 5, "resolution": "480p"},
        {"duration": 10, "resolution": "720p", "file_ids": [picture]},
        {"duration": 8, "resolution": "480p", "generate_audio": False},
    ]
    for who in (owner, editor):  # an editor's runs on their own week: the same price
        for n, ask in enumerate(asks):
            body = {"brand_id": brand, "prompt": f"A cat on a desk, take {n}.", **ask}
            shown = who.post("/clips/estimate", json=body)
            assert shown.status_code == 200, shown.text
            since = _last(db)
            made = who.post("/clips", json=body)
            assert made.status_code == 201, made.text
            _drain(app, db, providers)
            charged = _charged(db, since)
            assert charged == Decimal(str(shown.json()["credits"])), (ask, shown.json(), charged)


def _rate(client) -> float:
    """What Enhance and Draft show: one Claude call at the catalogue's rate."""
    return next(r for r in client.get("/credits/rates").json()
                if r["kind"] == "write-claude")["credits_per_unit"]  # fmt: skip


def test_enhance_and_draft_charge_the_rate_they_show(app, db, owner, editor, setup):  # noqa: F811
    from app.providers import get_providers

    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    url = f"/projects/{setup['project']}/script"
    for who, press in ((editor, "enhance"), (owner, "draft")):
        shown = _rate(who)
        since = _last(db)
        made = who.post(f"{url}/{press}")
        assert made.status_code == 201, made.text
        _drain(app, db, providers)
        _is_the_charge(price(Decimal(str(shown))), _charged(db, since))
    draft = owner.get(f"{url}/drafts").json()[0]
    since = _last(db)
    used = owner.post(f"{url}/drafts/{draft['job_id']}/{draft['n']}/use")  # Use this draft: free
    assert used.status_code == 201, used.text
    assert _charged(db, since) == 0


def test_writing_a_script_charges_its_estimate_with_the_cast_read(app, db, owner, editor):
    from tests.test_script_preview import _work
    from tests.test_script_write import _bulk

    for who in (owner, editor):  # an editor's own script runs on their week: the same price
        sid = _bulk(who, 1)[0]
        shown = who.get(f"/scripts/{sid}/write/estimate").json()["credits"]
        since = _last(db)
        assert who.post(f"/scripts/{sid}/write").status_code == 201
        _work(app, db)
        _is_the_charge(price(Decimal(str(shown))), _charged(db, since))  # write + cast read


def test_song_directions_charge_what_the_version_shows(app, db, owner, song):  # noqa: F811
    from tests.test_song_directions import SCRIPT, _version
    from tests.test_song_takes import _work

    shown = _version(owner, song)["directions_estimate_credits"]
    since = _last(db)
    assert owner.post(f"{song}/directions", json={"source": SCRIPT}).status_code == 201
    _work(app, db)
    _is_the_charge(price(Decimal(str(shown))), _charged(db, since))


def test_improve_and_variations_charge_what_they_show(app, db, owner, editor):
    from tests.test_script_preview import _work
    from tests.test_script_write import _bulk

    brand = owner.get("/brands").json()[0]["id"]
    for who in (owner, editor):  # Improve: one Claude call at the rate it shows
        since = _last(db)
        body = {"brand_id": brand, "prompt": "Mia buys bitcoin at dawn."}
        assert who.post("/clips/improve", json=body).status_code == 201
        _work(app, db)
        _is_the_charge(price(Decimal(str(_rate(who)))), _charged(db, since))
    sid = _bulk(owner, 1)[0]  # Write variations: two versions, then the cast read, one price
    owner.post(f"/scripts/{sid}/write")
    _work(app, db)
    assert owner.post(f"/scripts/{sid}/drafts/0/approve").status_code == 200
    shown = owner.get(f"/scripts/{sid}/variations/estimate").json()["credits"]
    since = _last(db)
    made = owner.post(f"/scripts/{sid}/variations", json={})
    assert made.status_code == 201, made.text
    _work(app, db)
    _is_the_charge(price(Decimal(str(shown))), _charged(db, since))


def test_an_owners_rate_that_isnt_whole_is_still_never_shown_below_the_charge(
    app,
    db,
    owner,
    editor,
    setup,  # noqa: F811
):
    """The screens round a rate up (Improve rounded it to the nearest, Drafts to a tenth): at
    2.4 a call charges 2.4 and is shown as 3."""
    from app.providers import get_providers

    owner.put("/credits/rates/write-claude", json={"unit": "call", "credits_per_unit": 2.4})
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    since = _last(db)
    assert editor.post(f"/projects/{setup['project']}/script/enhance").status_code == 201
    _drain(app, db, providers)
    charged = _charged(db, since)
    assert charged == Decimal("2.4") and price(charged) == 3
