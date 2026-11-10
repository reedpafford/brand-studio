"""Omni 1.2 straight from Google (app/providers/google.py), against a mock of Google's API as
its docs describe it (aistudio.google.com/docs/omni and the pages google.py names): no real
or paid call, and no key."""

import base64
import json
from decimal import Decimal

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from app import clip_takes
from app.catalogue import get_model, provider_for
from app.credits import estimate
from app.models.accounts import User
from app.models.jobs import Usage
from app.providers import NoKey, NotStarted, get_providers
from app.providers.google import GoogleProvider, body
from app.routes.jobs import enqueue
from app.settings import Settings, get_settings
from app.worker import run_once
from tests.helpers import MP4

BASE = "https://generativelanguage.test/v1beta"
KEY = "g-test-key"
OMNI = "gemini-omni-1.2"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n-sheet").decode()
CLIP = "data:video/mp4;base64," + base64.b64encode(MP4).decode()
TAKE = {"prompt": "She lifts the pouch.\nOne continuous shot, no scene cuts.", "duration": 8,
        "resolution": "720p", "aspect_ratio": "9:16"}  # fmt: skip
VIDEO = {"type": "video", "mime_type": "video/mp4", "data": base64.b64encode(MP4).decode()}
SAFETY = {"code": "safety", "message": "Request blocked due to safety violations (harmful "
          "content). Please modify your input and retry."}  # fmt: skip
USED = {"total_input_tokens": 2000, "total_output_tokens": 46336,  # 8 s at 720p: 5,792 a second
        "output_tokens_by_modality": [{"modality": "video", "tokens": 46336}]}  # fmt: skip


def _done(**more) -> dict:
    steps = [{"type": "user_input", "content": [{"type": "text", "text": "…"}]},
             {"type": "model_output", "content": [VIDEO]}]  # fmt: skip
    return {"id": "v1_abc", "status": "completed", "model": "gemini-omni-1.2-flash",
            "object": "interaction", "steps": steps, "usage": USED, **more}  # fmt: skip


def _google(handler, key: str = KEY, **more) -> tuple[GoogleProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request):
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return GoogleProvider(BASE, key, client, ("googleusercontent.com",), **more), seen


def _answers(*answers):
    """Each GET of the interaction gets the next answer (the last one from then on)."""
    left = list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "v1_abc", "status": "in_progress"})
        return httpx.Response(200, json=left.pop(0) if len(left) > 1 else left[0])

    return handler


@pytest.fixture
def direct(monkeypatch):
    """A Google key is set: Omni 1.2's road is Google's."""
    monkeypatch.setattr(get_settings(), "google_api_key", SecretStr(KEY))


def test_a_take_is_sent_as_googles_docs_say_with_the_key_in_a_header_only():
    google, seen = _google(_answers({}))
    job = {"model": OMNI, "input": {**TAKE, "reference_images": [PNG, PNG]}}
    assert google.submit("video", job) == "v1_abc"  # the interaction's id is the job's
    sent = json.loads(seen[0].content)
    assert (seen[0].method, str(seen[0].url)) == ("POST", f"{BASE}/interactions")
    assert seen[0].headers["x-goog-api-key"] == KEY and KEY not in str(seen[0].url)
    picture = {"type": "image", "mime_type": "image/png", "data": PNG.split(",")[1]}
    assert sent == {
        "model": "gemini-omni-1.2-flash",
        "input": [picture, picture, {"type": "text", "text": TAKE["prompt"]}],  # as written
        "response_format": {"type": "video", "delivery": "uri", "aspect_ratio": "9:16",
                            "resolution": "720p", "duration": "8s"},
        "generation_config": {"video_config": {"task": "reference_to_video"}},
        "background": True,
    }  # fmt: skip


def test_a_prompt_alone_an_edit_and_a_start_frame_each_take_their_documented_shape():
    words = body("gemini-omni-1.2-flash", {**TAKE, "generate_audio": True})  # no sound switch
    assert words["input"] == TAKE["prompt"] and "generation_config" not in words
    assert "audio" not in json.dumps(words)
    edit = body("m", {"prompt": "Make it night. Keep everything else the same.",
                      "resolution": "720p", "video": CLIP})  # fmt: skip
    clip = {"type": "video", "mime_type": "video/mp4", "data": CLIP.split(",")[1]}
    said = {"type": "text", "text": "Make it night. Keep everything else the same."}
    assert edit["input"] == [{"type": "user_input", "content": [clip, said]}]
    assert edit["generation_config"] == {"video_config": {"task": "edit"}}
    assert edit["response_format"] == {"type": "video", "delivery": "uri", "resolution": "720p"}
    framed = body("m", {**TAKE, "image": PNG, "last_frame": PNG})
    assert framed["generation_config"] == {"video_config": {"task": "image_to_video"}}
    assert [c["type"] for c in framed["input"]] == ["image", "image", "text"]
    assert body("m", TAKE, background=False)["background"] is False


def test_a_start_frame_with_references_or_no_key_sends_nothing():
    google, seen = _google(_answers({}))
    both = {"model": OMNI, "input": {**TAKE, "image": PNG, "reference_images": [PNG]}}
    with pytest.raises(RuntimeError, match="never two of them") as refused:
        google.submit("video", both)
    assert clip_takes.invalid(repr(refused.value))  # as Replicate's 422: never sent again as it is
    with pytest.raises(RuntimeError, match="isn't made through Google"):
        google.submit("video", {"model": "seedance-2.5", "input": TAKE})
    keyless, unsent = _google(_answers({}), key="")
    for call in (lambda: keyless.submit("video", {"model": OMNI, "input": TAKE}),
                 lambda: keyless.poll("v1_abc"), lambda: keyless.cancel("v1_abc")):  # fmt: skip
        with pytest.raises(NoKey):
            call()
    assert seen == [] and unsent == []


def test_checking_reads_running_done_and_failed_and_the_cost_is_the_tokens_google_counted():
    waiting = {"id": "v1_abc", "status": "in_progress"}
    google, seen = _google(_answers(waiting, _done()))
    assert google.poll("v1_abc").state == "running"
    made = google.poll("v1_abc")
    assert (made.state, made.files) == ("succeeded", [f"{BASE}/interactions/v1_abc"])
    assert made.output == {}  # nothing of the money or the video in what editors see
    # 46,336 video tokens at $12.00 and 2,000 input tokens at $1.50, per million: 8 s of 720p
    assert [(u.units, u.unit, u.cost_usd, u.estimated) for u in made.usage] == [
        (Decimal("8.0"), "second", Decimal("0.5590"), False)]  # fmt: skip
    assert google.fetch(made.files[0]) == (MP4, "video/mp4")
    assert [str(r.url) for r in seen] == [f"{BASE}/interactions/v1_abc"] * 3
    assert all(r.headers["x-goog-api-key"] == KEY and KEY not in str(r.url) for r in seen)
    google.cancel("v1_abc")
    assert (seen[-1].method, str(seen[-1].url)) == ("POST", f"{BASE}/interactions/v1_abc/cancel")
    stopped, _ = _google(_answers({"id": "v1_abc", "status": "cancelled"}))
    assert (stopped.poll("v1_abc").state, stopped.poll("v1_abc").usage) == ("failed", [])


def test_a_take_google_counted_no_tokens_for_costs_its_seconds_at_the_catalogue_price():
    asked = {"type": "video", "duration": "8s", "resolution": "720p"}
    google, _ = _google(_answers(_done(usage=None, response_format=asked)))
    price = get_model(OMNI, listed=True).via.usd["720p"]
    assert price == Decimal("0.07")  # aistudio.google.com/docs/pricing, read 10 Nov 2026
    assert [(u.units, u.cost_usd, u.estimated) for u in google.poll("v1_abc").usage] == [
        (8, 8 * price, True)]  # fmt: skip
    silent, _ = _google(_answers(_done(usage=None)))  # nor its length: the worker's estimate
    assert silent.poll("v1_abc").usage == []


def test_a_video_given_as_a_file_waits_until_ready_and_downloads_with_the_key_at_google_only():
    link = {"type": "video", "mime_type": "video/mp4",
            "uri": f"{BASE}/files/f-9:download?alt=media"}  # fmt: skip
    states = ["PROCESSING", "ACTIVE"]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"{BASE}/interactions/v1_abc":
            return httpx.Response(200, json=_done(steps=[
                {"type": "user_input", "content": [VIDEO]},  # an edit's own clip: never the take
                {"type": "model_output", "content": [link]}]))  # fmt: skip
        if url == f"{BASE}/files/f-9":
            return httpx.Response(200, json={"name": "files/f-9", "state": states.pop(0)})
        if url == f"{BASE}/files/f-9:download?alt=media":
            return httpx.Response(302, headers={"location": "https://dl.googleusercontent.com/v"})
        if url == "https://dl.googleusercontent.com/v":
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        if url == f"{BASE}/files/away:download?alt=media":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/v"})
        return httpx.Response(404)

    google, seen = _google(handler)
    assert google.poll("v1_abc").state == "running"  # its file is still being processed
    made = google.poll("v1_abc")
    assert made.files == [f"{BASE}/files/f-9:download?alt=media"]
    assert google.fetch(made.files[0]) == (MP4, "video/mp4")
    at_google = [r for r in seen if str(r.url).startswith(BASE)]
    assert all(r.headers["x-goog-api-key"] == KEY for r in at_google)
    assert "x-goog-api-key" not in seen[-1].headers  # sent on to a file host: no key
    assert seen[-1].url.host == "dl.googleusercontent.com"
    for url in (f"{BASE}/files/away:download?alt=media", "https://elsewhere.example/v",
                "https://generativelanguage.test.evil.example/v1beta/files/x"):  # fmt: skip
        with pytest.raises(RuntimeError, match="Refusing to download"):
            google.fetch(url)
    assert not any(r.url.host.endswith("example") for r in seen)  # never asked, with a key or not


@pytest.mark.parametrize("how", ["at once", "in the background"])
def test_a_safety_block_is_our_refusal_never_sent_again_as_it_was(how):
    """Google's block (docs/safety-settings: a 400, or a failed interaction with the same code
    in `errors`) reads as Replicate's Omni refusals do: refused, by the safety filter, in
    Google's own words, and never a "try again"."""
    from app.worker import _plain

    class Failed:
        kind, input = "video", {}

    if how == "at once":
        google, _ = _google(lambda r: httpx.Response(400, json={"error": SAFETY}))
        with pytest.raises(RuntimeError) as blocked:
            google.submit("video", {"model": OMNI, "input": TAKE})
        detail = repr(blocked.value)
    else:
        failed = {"id": "v1_abc", "status": "failed", "errors": [SAFETY]}
        detail = _google(_answers(failed))[0].poll("v1_abc").error
    Failed.error_detail = detail
    assert clip_takes.why_failed(Failed) == "refused"
    how_said = ("blocked by the service's safety filter (it said: Request blocked due to safety "
                "violations (harmful content))")  # fmt: skip
    assert clip_takes.refused_how(detail) == how_said
    assert _plain(Failed, detail) == clip_takes.REFUSED_SAID.format(how_said)


def test_googles_other_blocks_and_bad_requests_read_as_refused_and_invalid():
    class Failed:
        error_detail = ""

    def why(status: int, error: dict) -> str:
        google, _ = _google(lambda r: httpx.Response(status, json={"error": error}))
        with pytest.raises(RuntimeError) as said:
            google.submit("video", {"model": OMNI, "input": TAKE})
        Failed.error_detail = repr(said.value)
        return clip_takes.why_failed(Failed)

    blocked = {"code": "blocklist", "message": "Input blocked: a term on the blocklist."}
    assert why(400, blocked) == "refused"
    assert why(400, {"code": "image_safety", "message": "The image was blocked."}) == "refused"
    bad = {"code": "invalid_request", "message": "The value '20s' is not supported for 'duration'."}
    assert why(400, bad) == "invalid"
    assert clip_takes.invalid(Failed.error_detail) == bad["message"]
    assert why(403, {"code": "permission_denied", "message": "Billing is off."}) == ""


@pytest.mark.parametrize("status", [429, 503])
def test_a_rate_limit_or_an_overloaded_google_is_busy_never_a_failed_take(status, app, owner, db,
                                                                         direct):  # fmt: skip
    error = {"error": {"code": "rate_limit_exceeded", "message": "Slow down."}}
    google, seen = _google(lambda r: httpx.Response(status, json=error))
    with pytest.raises(NotStarted) as busy:
        google.submit("video", {"model": OMNI, "input": TAKE})
    assert clip_takes.BUSY_SAID.search(repr(busy.value))  # a take that ends so is tried again
    job = _job(db)
    run_once(db, {"google": google}, app.state.storage)
    db.refresh(job)
    assert (job.status, job.input["busy"]) == ("queued", 1)  # nothing started: it waits


def test_a_take_googles_rate_limit_stopped_midway_reads_as_busy():
    class Failed:
        pass

    limit = {"code": "rate_limit_exceeded", "message": "Resource exhausted."}
    google, _ = _google(_answers({"id": "v1_abc", "status": "failed", "errors": [limit]}))
    Failed.error_detail = google.poll("v1_abc").error
    assert clip_takes.why_failed(Failed) == "busy"


def test_the_key_never_reaches_an_error_text():
    said = {"error": {"code": "authentication", "message": f"API key {KEY} is not valid."}}
    google, _ = _google(lambda r: httpx.Response(401, json=said))
    with pytest.raises(RuntimeError) as refused:
        google.submit("video", {"model": OMNI, "input": TAKE})
    assert KEY not in repr(refused.value) and "[key]" in repr(refused.value)

    def dropped(request):
        raise httpx.ConnectError(f"no route for {KEY}")

    with pytest.raises(Exception) as lost:  # noqa: PT011 - NetworkError, whatever it says
        _google(dropped)[0].poll("v1_abc")
    assert KEY not in repr(lost.value)
    assert KEY not in repr(Settings(google_api_key=KEY))


# --- Routing: Google only while its key is set, and every price follows the road taken -------


def _job(db):
    user = db.query(User).first()
    return enqueue(db, user, "video", {"model": OMNI, "input": TAKE}, units=8, provider="replicate")


def test_omni_goes_through_replicate_at_its_price_with_no_google_key(app, owner, db):
    assert not get_settings().google_on
    assert provider_for(OMNI, "replicate") == "replicate"
    assert get_model(OMNI).usd_per_unit("720p") == Decimal("0.11")
    job = _job(db)
    assert (job.provider, job.credits) == ("replicate", Decimal("8.56"))  # 8 s at 1.07 credits


def test_with_a_google_key_omni_goes_to_google_and_its_prices_are_googles(app, owner, db, direct):
    assert provider_for(OMNI, "replicate") == "google"
    omni = get_model(OMNI)
    assert (omni.direct, omni.usd_per_unit("720p")) == (True, Decimal("0.07"))
    assert omni.usd_per_unit("720p", edit=True) == Decimal("0.07")  # an edit: a take's rate
    assert omni.provider_model == "google/gemini-omni-1.2-flash"  # Replicate's name is kept
    job = _job(db)
    assert (job.provider, job.credits) == ("google", Decimal("5.44"))  # 8 s at 0.68 credits
    quote = estimate(db, job.workspace_id, "video", Decimal(8), {"model": OMNI, "input": TAKE})
    assert quote == job.credits  # the estimate before the press is the road's own
    prices = {p["id"]: p for p in owner.get("/models/prices").json()}
    assert prices[OMNI]["price_per_unit_usd"]["720p"] == "0.07"
    assert "aistudio.google.com/docs/pricing" in prices[OMNI]["price_source"]
    assert "usd" not in json.dumps(owner.get(f"/models/{OMNI}").json())  # no dollars for editors


def test_only_omni_on_replicates_lane_moves(app, owner, db, direct):
    assert provider_for("seedance-2.5", "replicate") == "replicate"
    assert provider_for(OMNI, "fake") == "fake"  # a test's own lane
    assert provider_for(OMNI, "replicate-samples") == "replicate-samples"
    assert provider_for(None, "claude") == "claude"
    assert get_model("seedance-2.5") is get_model("seedance-2.5", listed=True)
    assert get_model(OMNI, listed=True).usd_per_unit("720p") == Decimal("0.11")


def test_the_switch_alone_routes_where_the_key_is_only_the_workers(app, owner, db, monkeypatch):
    """deploy/docker-compose.yml: the API never holds the key; it gets BS_GOOGLE_DIRECT."""
    monkeypatch.setattr(get_settings(), "google_direct", "yes")
    assert _job(db).provider == "google"
    monkeypatch.setattr(get_settings(), "google_direct", "")
    assert _job(db).provider == "replicate"  # the key (and so the switch) taken away: back


def test_a_google_take_runs_is_saved_and_charged_what_google_billed(app, owner, db, direct):
    google, seen = _google(_answers({"id": "v1_abc", "status": "in_progress"}, _done()))
    job = _job(db)
    for _ in range(3):
        run_once(db, {"google": google}, app.state.storage)
    db.refresh(job)
    assert (job.status, job.provider_ref) == ("succeeded", "v1_abc")
    assert owner.get(f"/files/{job.output['file_ids'][0]}").content == MP4
    usage = db.query(Usage).one()
    assert (usage.provider, usage.units, usage.cost_usd, usage.estimated) == (
        "google", 8, Decimal("0.5590"), False)  # fmt: skip
    assert job.credits == Decimal("5.438")  # the real cost in credits: under the 5.44 shown
    assert json.loads(seen[0].content)["model"] == "gemini-omni-1.2-flash"


def test_replicate_prices_its_own_omni_take_at_its_own_price_whatever_road_is_open(direct):
    """A take already on Replicate when the key is set is still recorded at Replicate's price."""
    from app.providers.replicate import ReplicateProvider

    done = {"id": "o1", "status": "succeeded", "version": None, "output": "https://x.test/o.mp4",
            "model": "google/gemini-omni-1.2-flash", "input": {**TAKE},
            "metrics": {"video_output_duration_seconds": 8}}  # fmt: skip
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=done)))
    made = ReplicateProvider("https://replicate.test/v1", client, token="t").poll("o1")
    assert made.usage[0].cost_usd == 8 * Decimal("0.11")


def test_the_stand_in_answers_for_omni_on_either_road_with_no_key(app, owner, db, monkeypatch):
    providers = get_providers(Settings(fake_providers=True, google_api_key=""), app.state.storage)
    assert type(providers["google"]) is type(providers["replicate"])  # the same free stand-in
    made = [_job(db)]
    monkeypatch.setattr(get_settings(), "google_direct", "yes")
    made.append(_job(db))
    for _ in range(3):
        run_once(db, providers, app.state.storage)
    for job in made:
        db.refresh(job)
    assert [(j.provider, j.status) for j in made] == [("replicate", "succeeded"),
                                                      ("google", "succeeded")]  # fmt: skip
    assert db.query(Usage).count() == 0  # no real dollars from a stand-in
    real = get_providers(Settings(google_api_key=""), app.state.storage)["google"]
    with pytest.raises(NoKey):  # a job left on Google's lane after the key went: unsent
        real.submit("video", {"model": OMNI, "input": TAKE})
