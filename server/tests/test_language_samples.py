"""A language's sample test (flows VS1, owner only): Test <language> writes one short script
in it for a brand; the owner approves it (the language switches on for editors) or rejects
it. All on the free stand-ins (no paid calls)."""

from pydantic import SecretStr

from app import language_samples, languages
from app.models.jobs import Job
from tests.test_song_takes import _work


def _brand(owner):
    return owner.get("/brands").json()[0]["id"]


def test_a_test_is_written_read_and_approved_then_editors_may_pick_it(app, db, owner, editor):
    app.state.settings.fake_providers = True
    brand = _brand(owner)
    shown = owner.get("/languages/es/sample").json()
    assert shown["status"] == "none" and shown["credits"] > 0 and not shown["language"]["on"]
    assert editor.get("/languages/es/sample").status_code == 403  # the owner's page
    no = owner.patch("/languages/es", json={"on": True})
    assert (no.status_code, no.json()["detail"]) == (409, language_samples.NO_SAMPLE)

    made = owner.post("/languages/es/sample", json={"brand_id": brand})
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "making"
    again = owner.post("/languages/es/sample", json={"brand_id": brand})
    assert (again.status_code, again.json()["detail"]) == (409, language_samples.ALREADY)
    _work(app, db, ticks=2)
    ready = owner.get("/languages/es/sample").json()
    assert ready["status"] == "ready" and "(Spanish)" in ready["text"]
    job = db.query(Job).filter(Job.input["step"].as_string() == language_samples.STEP).one()
    assert "<language>Spanish</language>" in job.input["prompt"]
    assert "## Language sample" in job.input["system"][0]

    assert owner.patch("/languages/es", json={"on": True}).json()["on"]  # Approve
    assert {"id": "es", "name": "Spanish", "on": True} in editor.get("/languages").json()
    script = editor.post("/scripts", json={"brand_id": brand, "title": "Hola", "language": "es"})
    assert script.status_code == 201 and script.json()["language"] == "es"
    assert not owner.patch("/languages/es", json={"on": False}).json()["on"]  # Switch off
    off = editor.post("/scripts", json={"brand_id": brand, "title": "Hola", "language": "es"})
    assert (off.status_code, off.json()["detail"]) == (409, languages.OFF.format("Spanish"))


def test_a_rejected_sample_keeps_it_off_with_undo_and_test_again(app, db, owner):
    app.state.settings.fake_providers = True
    brand = _brand(owner)
    early = owner.patch("/languages/fr/sample", json={"rejected": True})
    assert (early.status_code, early.json()["detail"]) == (409, language_samples.NO_SAMPLE)
    owner.post("/languages/fr/sample", json={"brand_id": brand})
    _work(app, db, ticks=2)
    owner.patch("/languages/fr", json={"on": True})
    rejected = owner.patch("/languages/fr/sample", json={"rejected": True}).json()
    assert rejected["status"] == "rejected" and not rejected["language"]["on"]  # back off
    assert owner.patch("/languages/fr", json={"on": True}).status_code == 409
    undone = owner.patch("/languages/fr/sample", json={"rejected": False}).json()
    assert undone["status"] == "ready" and undone["language"]["on"]  # Undo: on, as it was
    owner.patch("/languages/fr/sample", json={"rejected": True})
    assert owner.post("/languages/fr/sample", json={"brand_id": brand}).json()["status"] == "making"
    english = owner.post("/languages/en/sample", json={"brand_id": brand})
    assert (english.status_code, english.json()["detail"]) == (409, language_samples.ENGLISH)
    assert owner.patch("/languages/en", json={"on": False}).status_code == 409


def test_real_tests_on_the_test_site_go_real_until_the_budget(app, db, owner, monkeypatch):
    """Reed, 2026-10-29: with the stand-ins on, only a language's test goes to real Claude,
    and only while it fits the test budget; nothing is sent here."""
    from app.providers import REAL_TESTS, get_providers, tests_on
    from app.settings import Settings

    monkeypatch.setenv("STUDIO_ANTHROPIC_KEY", "test-key")
    assert not tests_on(Settings(fake_providers=True))  # off until switched on
    providers = get_providers(Settings(fake_providers=True, real_language_samples=True))
    assert providers[REAL_TESTS].paid and not providers["claude"].paid  # the rest: stand-ins

    settings = app.state.settings
    settings.fake_providers, settings.real_language_samples = True, True
    settings.language_samples_budget_usd = 0.5  # one test (about $0.31)
    brand = _brand(owner)
    assert owner.get("/languages/de/sample").json()["test_site"] == language_samples.REAL_NOTE
    owner.post("/languages/de/sample", json={"brand_id": brand})
    assert db.query(Job).order_by(Job.id.desc()).first().provider == REAL_TESTS
    assert owner.get("/languages/it/sample").json()["test_site"] == language_samples.USED_UP
    owner.post("/languages/it/sample", json={"brand_id": brand})  # past the budget
    newest = db.query(Job).order_by(Job.id.desc()).first()
    assert newest.input["language"] == "it" and newest.provider == "claude"  # a stand-in


def test_with_real_tests_on_only_the_test_goes_real_and_no_key_means_a_stand_in(app, db, owner):
    """QA-4 and Flow-QA on #972: every other script call stays a stand-in while the switch is
    on; switched on without the key, the test's lane writes a stand-in, never a failed job."""
    from app.providers import REAL_TESTS, get_providers
    from app.providers.fake_local import FakeWriter

    settings = app.state.settings
    settings.fake_providers, settings.real_language_samples = True, True
    settings.language_samples_budget_usd, settings.anthropic_key = 2, SecretStr("")  # no key
    assert isinstance(get_providers(settings)[REAL_TESTS], FakeWriter)
    brand = _brand(owner)
    words = {"brand_id": brand, "title": "Paws", "text": "MAYA: Hi."}
    script = owner.post("/scripts", json=words).json()
    enhance = owner.post(f"/scripts/{script['id']}/drafts/0/enhance")
    assert enhance.status_code == 201, enhance.text
    assert db.get(Job, enhance.json()["id"]).provider == "claude"  # another call: a stand-in
    owner.post("/languages/nl/sample", json={"brand_id": brand})
    assert db.query(Job).order_by(Job.id.desc()).first().provider == REAL_TESTS
    _work(app, db, ticks=2)
    assert owner.get("/languages/nl/sample").json()["status"] == "ready"  # a stand-in test
