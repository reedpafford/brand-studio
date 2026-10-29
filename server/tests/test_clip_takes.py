"""Clip takes (mocked Replicate, no paid calls), approval and the free stitch (real ffmpeg)."""

import json
import subprocess

import httpx2 as httpx
import pytest

from app.clip_takes import in_english
from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import _usd_keys, approved_plan, assert_hidden, assert_no_dollars, with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_project_clips import _answer, _prompt
from tests.test_replicate import BASE


def _mp4(color: str) -> bytes:
    """A real 1-second MP4, so the stitch runs ffmpeg for real."""
    args = (
        f"-v error -f lavfi -i color=c={color}:s=64x64:d=1 -f lavfi -i anullsrc=r=44100:cl=mono "
        "-t 1 -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "
        "-movflags frag_keyframe+empty_moov -f mp4 pipe:1"
    ).split()
    done = subprocess.run(["ffmpeg", *args], capture_output=True, check=True)  # noqa: S603, S607
    return done.stdout


class FakeSeedance:
    """Each submit is a new prediction that is done on its first check, with its own video."""

    def __init__(self, videos: list[bytes]):
        self.videos, self.requests, self.n = videos, [], 0

    def __call__(self, request):
        self.requests.append(request)
        url = str(request.url)
        if request.method == "POST":
            self.n += 1
            return httpx.Response(201, json={"id": f"p{self.n}", "status": "starting"})
        if "/predictions/p" in url:
            n = url.rsplit("p", 1)[1]
            out = f"https://replicate.delivery/{n}.mp4"
            metrics = {"predict_time": 9, "video_output_duration_seconds": 5}
            return httpx.Response(
                200, json={"id": f"p{n}", "status": "succeeded", "output": out, "metrics": metrics}
            )
        if url.startswith("https://replicate.delivery/"):
            n = int(url.rsplit("/", 1)[1].split(".")[0])
            return httpx.Response(
                200, content=self.videos[n - 1], headers={"content-type": "video/mp4"}
            )
        return httpx.Response(404)


@pytest.fixture
def clip(app, db, editor, setup):  # noqa: F811
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    with_sheet(db, mom)
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom]})
    bd = json.loads(json.dumps(BREAKDOWN))
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mom}"]
    approved_plan(db, f"/projects/{setup['project']}")  # shots come from a plan (1b)
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(bd))
    editor.post(f"/projects/{setup['project']}/clips/prompts")
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], _prompt())))
    return editor.get(f"/projects/{setup['project']}/clips").json()[0]


def _work(app, db, fake):
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(2):
        run_once(
            db,
            {"replicate": ReplicateProvider(BASE, client)},
            app.state.storage,
            only={"replicate"},
        )  # the video lane, as live: Claude's jobs wait for theirs


def test_takes_pick_approve_and_stitch(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    assert editor.post(f"{base}/video").json()["detail"].startswith("Approve every clip")
    assert editor.post(f"{url}/approve").status_code == 409  # no take yet
    job = editor.post(f"{url}/generate")
    assert job.status_code == 201 and job.json()["credits"] == 5  # 5 s at 480p
    assert editor.post(f"{url}/generate").status_code == 409  # one at a time
    fake = FakeSeedance([_mp4("red"), _mp4("blue")])
    _work(app, db, fake)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    assert sent["prompt"] == in_english(clip["prompt"]) and sent["aspect_ratio"] == "9:16"
    assert sent["duration"] == 5 and sent["resolution"] == "480p"
    assert len(sent["reference_images"]) == 2  # Mom's sheet, the screen (lossless)

    editor.post(f"{url}/generate")
    _work(app, db, fake)
    got = editor.get(f"{base}/clips").json()[0]
    takes = got["takes"]
    assert [t["number"] for t in takes] == [1, 2] and got["picked_take_id"] == takes[1]["id"]
    picked = editor.post(f"{url}/takes/{takes[0]['id']}/pick").json()
    assert picked["picked_take_id"] == takes[0]["id"] and picked["approved"] is False
    assert editor.post(f"{url}/approve").json()["approved"] is True

    video = editor.post(f"{base}/video")
    assert video.status_code == 201, video.text
    assert video.json()["take_ids"] == [takes[0]["id"]] and video.json()["out_of_date"] is False
    data = editor.get(f"/files/{video.json()['file_id']}").content
    assert data[4:8] == b"ftyp" or b"ftyp" in data[:64]
    assert_no_dollars(editor, [f"{base}/clips", f"{base}/video", f"/jobs/{job.json()['id']}"])
    for r in (picked, video.json(), job.json()):
        assert not _usd_keys(r)
    editor.post(f"{url}/takes/{takes[1]['id']}/pick")  # a different take: the video is old
    assert editor.get(f"{base}/video").json()["out_of_date"] is True
    assert db.query(Job).filter_by(kind="video").count() == 2


def test_clip_with_problems_and_other_workspace(app, editor, outsider, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    assert_hidden(outsider, [("POST", f"{url}/generate"), ("POST", f"{base}/video")])
    broken = {"prompt": "too short", "references": clip["references"]}
    editor.put(url, json=broken)
    assert editor.post(f"{url}/generate").json()["detail"] == "Fix this clip's problems first."
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(f"{url}/generate").status_code == 503
    finally:
        app.state.settings.generation_enabled = True
    assert editor.get(f"{base}/video").status_code == 404


def test_stale_and_replaced_clips(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    editor.post(f"{url}/generate")
    one = {"clip_id": clip["clip_id"]}
    r = editor.post(f"{base}/clips/prompts", json=one)  # a take is on its way: wait for it
    assert r.status_code == 409 and "Wait for the clips" in r.json()["detail"]
    _work(app, db, FakeSeedance([_mp4("red")]))
    assert len(editor.get(f"{base}/clips").json()[0]["takes"]) == 1
    old = editor.get(f"{base}/clips").json()[0]
    nothing = editor.post(f"{base}/clips/prompts")  # none is stale: nothing to rewrite
    assert (nothing.status_code, nothing.json()["detail"]) == (409, "No clip needs new prompts.")
    assert editor.post(f"{base}/clips/prompts", json=one).status_code == 201  # one clip
    _run(
        app,
        db,
        FakeClaude(
            {
                "clips": [
                    {
                        **{k: old[k] for k in ("clip_id", "seconds", "prompt")},
                        "references": old["references"],
                    }
                ]
            }
        ),
    )
    new = editor.get(f"{base}/clips").json()[0]
    assert new["id"] == old["id"] and len(new["takes"]) == 1  # the take stays (Reed, #503)
    assert new["picked_take_id"] == old["picked_take_id"] and new["approved"] is False
    url = f"{base}/clips/{new['id']}"

    script = editor.get(f"{base}/script").json()["text"]
    editor.put(f"{base}/script", json={"text": script + "\nMOM: Fine."})
    assert editor.get(f"{base}/clips").json()[0]["stale"] is True
    r = editor.post(f"{url}/generate")
    assert r.status_code == 409 and "older breakdown" in r.json()["detail"]


def test_money_rules(app, db, owner, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    used = editor.get(base).json()["credits_used"]  # the Claude steps so far
    job = editor.post(f"{url}/generate").json()
    assert job["credits"] == clip["seconds"] == 5  # 1 credit per second at 480p
    assert editor.get(base).json()["credits_used"] == pytest.approx(used + 5)
    _work(app, db, FakeSeedance([_mp4("red")]))

    limits = {"max_planned_seconds": 170, "weekly_quick_clip_credits": 150}
    owner.put("/credits/limits", json={**limits, "per_video_max_credits": int(used) + 9})
    over = editor.post(f"{url}/generate")  # 5 more would pass the per-video cap
    assert (over.status_code, over.json()["detail"]) == (409, "This video would go over its limit.")
    assert "$" not in over.json()["detail"]  # editors never see dollars
    mine = owner.post(f"{url}/generate")  # the cap holds for the owner too, in dollars
    assert mine.status_code == 409 and mine.json()["detail"].startswith(
        "This video would go over its $"
    )


def test_reference_without_a_picture(app, db, editor, setup, clip):  # noqa: F811
    voiceless = editor.post("/library/character", json={"name": "Ghost"}).json()["id"]
    project = f"/projects/{setup['project']}"
    editor.patch(project, json={"cast_ids": [*editor.get(project).json()["cast_ids"], voiceless]})
    refs = [*clip["references"], {"kind": "image", "id": f"char:{voiceless}", "role": "Ghost"}]
    with_ghost = {"prompt": clip["prompt"], "references": refs}
    from app.models.clips import ProjectClip

    row = db.get(ProjectClip, clip["id"])
    row.references, row.problems = with_ghost["references"], []  # as if Claude picked it
    db.commit()
    r = editor.post(f"{project}/clips/{clip['id']}/generate")
    assert (r.status_code, r.json()["detail"]) == (
        422,
        "Approve Ghost's sheet first.",  # a character with no approved sheet
    )


def test_clips_pane_support(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    assert clip["take_credits"] == 5  # what Make clip will cost, from the server
    job = editor.post(f"{url}/generate", json={"note": "Mom should look angrier."}).json()
    assert job["project_clip_id"] == clip["id"] and job["step"] == "clip_take"
    fake = FakeSeedance([_mp4("red")])
    _work(app, db, fake)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    lines = sent["prompt"].splitlines()
    assert lines[-2] == (
        "Change from the last take: Mom should look angrier. The spoken lines stay exactly as "
        "written above; nobody else speaks."
    )
    reworded = editor.post(f"{url}/generate", json={"note": 'Mom says "Hand it over."'})
    assert reworded.status_code == 422 and "nobody says in this clip" in reworded.json()["detail"]
    assert lines[0] == lines[-1]  # still opens and closes on the audio line
    assert editor.get(f"{base}/clips").json()[0]["prompt"] == clip["prompt"]  # note not kept

    assert editor.post(f"{url}/approve").json()["approved"] is True
    assert editor.delete(f"{url}/approve").json()["approved"] is False


class Refusing(FakeSeedance):
    """Seedance refusing every take for copyright (Kel's video, 2026-10-27)."""

    def __call__(self, request):
        if request.method == "GET" and "/predictions/p" in str(request.url):
            n = str(request.url).rsplit("p", 1)[1]
            error = "E005: the output video may be related to copyright restrictions"
            return httpx.Response(200, json={"id": f"p{n}", "status": "failed", "error": error})
        return super().__call__(request)


def test_a_copyright_refusal_says_what_to_do_and_warns_after_two(app, db, editor, setup, clip):  # noqa: F811
    from app.credits import credits_used
    from app.models.projects import Project

    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    before = credits_used(db, db.get(Project, setup["project"]))
    editor.post(f"{url}/generate")
    _work(app, db, Refusing([]))  # refused: tried again once on its own (P3)
    assert editor.get(f"/projects/{setup['project']}/clips").json()[0]["retrying"] == "refused"
    _work(app, db, Refusing([]))  # refused again: nothing more runs on its own
    retry, first = [j for j in editor.get("/jobs").json() if j["kind"] == "video"]
    assert (retry["auto"], retry["retry_of_id"], first["auto"]) == (True, first["id"], False)
    assert (
        retry["error"]
        == first["error"]
        == (
            "The video model thinks this clip looks too much like someone else's character or "
            "video. Try another look for Mom, or use Change this… on the opening shot. "
            "Nothing was charged."
        )
    )  # never "Ask the owner"
    shown = editor.get(f"/projects/{setup['project']}/clips").json()[0]
    assert shown["retrying"] is None
    assert shown["take_warning"].startswith("The last two takes of this clip were refused")
    assert credits_used(db, db.get(Project, setup["project"])) == before  # refused takes: free


class Busy(FakeSeedance):
    """Seedance too busy to finish a take (Producer, 2026-10-27)."""

    def __call__(self, request):
        if request.method == "GET" and "/predictions/p" in str(request.url):
            n = str(request.url).rsplit("p", 1)[1]
            error = "Service is temporarily unavailable. Please try again later."
            return httpx.Response(200, json={"id": f"p{n}", "status": "failed", "error": error})
        return super().__call__(request)


def test_a_busy_service_waits_then_tries_once_more_on_its_own(app, db, editor, setup, clip):  # noqa: F811
    from app.credits import credits_used
    from app.models.projects import Project

    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    project = db.get(Project, setup["project"])
    before = credits_used(db, project)
    editor.post(f"{url}/generate")
    price = credits_used(db, project) - before
    _work(app, db, Busy([]))
    retry = db.query(Job).filter(Job.auto.is_(True)).one()
    assert retry.status == "queued" and "wait_until" in retry.input  # a short wait first
    assert editor.get(f"/projects/{setup['project']}/clips").json()[0]["retrying"] == "busy"
    assert credits_used(db, project) == before + price  # held once, not twice
    retry.input = {**retry.input, "wait_until": ""}
    db.commit()
    _work(app, db, Busy([]))
    jobs = [j for j in editor.get("/jobs").json() if j["kind"] == "video"]
    assert [j["status"] for j in jobs] == ["failed", "failed"]  # never a second retry
    assert jobs[0]["error"] == (
        "The video service was busy and couldn't finish this. Nothing was charged; press "
        "Make clip to try again."
    )
    assert credits_used(db, project) == before  # both failed: the credits come back


class Flagged(FakeSeedance):
    """The video model's content check refusing a take (Reed's Iron Paws c4, jobs 990-1016)."""

    error = ("Prediction failed: Async prediction failed: ContentModerationError: Content "
             "flagged for: sexual")  # fmt: skip

    def __call__(self, request):
        if request.method == "GET" and "/predictions/p" in str(request.url):
            n = str(request.url).rsplit("p", 1)[1]
            return httpx.Response(
                200, json={"id": f"p{n}", "status": "failed", "error": self.error}
            )
        return super().__call__(request)


class Sensitive(Flagged):
    error = "ModelError: E005: The input or output was flagged as sensitive."


def test_a_moderation_refusal_says_why_and_offers_a_free_reword(app, db, editor, setup, clip):  # noqa: F811
    from app.credits import credits_used
    from app.models.clips import ProjectClip
    from app.models.projects import Project

    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    before = credits_used(db, db.get(Project, setup["project"]))
    db.get(ProjectClip, clip["id"]).free_fix_used = True  # used on this prompt already
    db.commit()
    editor.post(f"{url}/generate")
    _work(app, db, Flagged([]))
    (job,) = [j for j in editor.get("/jobs").json() if j["kind"] == "video"]
    assert job["error"] == (
        "The video model refused this prompt: it read it as sexual. Nothing was charged. "
        "Change the wording, then make it again."
    )
    assert "try again" not in job["error"].lower()
    shown = editor.get(f"/projects/{setup['project']}/clips").json()[0]  # Clips reopened
    assert shown["problems"] == [
        "The video model refused this prompt: it read it as sexual. Keep the story and the "
        "spoken lines; remove what reads as sexual."
    ]
    # P3: the free reword runs on its own (the press finds it), then the one retry
    assert (shown["free_fix_used"], shown["retrying"]) == (True, "refused")
    again = editor.post(f"{url}/generate")
    assert again.status_code == 409  # never the same prompt again
    fix = editor.post(f"{url}/fix").json()
    assert db.get(Job, fix["job"]["id"]).input["then_take"] == job["id"]
    queued = db.get(Job, fix["job"]["id"])
    assert "remove what reads as sexual" in queued.input["prompt"] and fix["job"]["credits"] == 0
    assert credits_used(db, db.get(Project, setup["project"])) == before

    body = {"prompt": shown["prompt"] + " ", "references": shown["references"]}
    assert editor.put(url, json=body).json()["problems"] == shown["problems"]  # a space: stays
    body["prompt"] = shown["prompt"].replace("Close-up, push in.", "Close-up.")  # their words
    assert editor.put(url, json=body).json()["problems"] == []  # new words: the refusal goes


def test_a_reworded_refusal_is_made_again_on_its_own_once(app, db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    editor.post(f"{url}/generate")
    _work(app, db, Flagged([]))
    mom = int(clip["references"][0]["id"].split(":")[1])
    reworded = clip["prompt"].replace("Close-up, push in.", "Close-up.")
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], reworded)))  # the free reword lands
    retry = db.query(Job).filter(Job.auto.is_(True)).one()
    assert retry.input["clip_prompt"] == reworded and retry.input["step"] == "clip_take"
    _work(app, db, FakeSeedance([_mp4("red")]))
    (shown,) = editor.get(f"/projects/{setup['project']}/clips").json()
    assert len(shown["takes"]) == 1 and shown["retrying"] is None
    assert shown["retried"] == "refused"  # "Tried again once on its own" stays
    editor.post(f"/projects/{setup['project']}/clips/{shown['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red"), _mp4("blue")]))
    (shown,) = editor.get(f"/projects/{setup['project']}/clips").json()
    assert len(shown["takes"]) == 2 and shown["retried"] is None  # a person's newer take


def test_a_sensitive_take_is_made_again_on_its_own_then_reworded(app, db, editor, setup, clip):  # noqa: F811
    from app.clip_takes import SENSITIVE

    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{url}/generate")
    _work(app, db, Sensitive([]))  # at random: made again on its own, as it is
    assert editor.get(clips).json()[0]["problems"] == []
    _work(app, db, Sensitive([]))
    jobs = [j for j in editor.get("/jobs").json() if j["kind"] == "video"]
    assert [j["error"] for j in jobs] == [SENSITIVE, SENSITIVE] and jobs[0]["auto"]
    (shown,) = editor.get(clips).json()  # it keeps failing: Reword it to pass
    assert shown["problems"][0].startswith("The video model refused this prompt: it read it as "
                                           "sensitive.")  # fmt: skip
    assert shown["free_fix_used"] is False and editor.post(f"{url}/generate").status_code == 409


def test_wording_flags_fix_themselves_with_undo(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    url = f"{clips}/{clip['id']}"
    flagged = clip["prompt"].replace("Summary: ", "Summary: Vertical 9:16, 480p. ")
    shown = editor.put(url, json={"prompt": flagged, "references": clip["references"]}).json()
    assert shown["prompt"] == clip["prompt"].replace("Summary: ", "Summary: Vertical. ")
    assert shown["auto_fix"] == {"fixed": ['removed "9:16"', 'removed "480p"'], "undone": False,
                                 "before": flagged}  # fmt: skip
    assert shown["problems"] == []
    undone = editor.post(f"{url}/auto-fix/undo").json()
    assert undone["prompt"] == flagged and undone["auto_fix"]["undone"] is True
    assert undone["problems"] == ["Advice: Writes aspect or resolution (those are settings)"]
    (shown,) = editor.get(clips).json()  # their words stay, as Advice: never a block
    assert shown["prompt"] == flagged and shown["problems"] == undone["problems"]
    assert editor.post(f"{url}/auto-fix/undo").status_code == 409
    edited = clip["prompt"].replace("Close-up, push in.", "Close-up.")
    shown = editor.put(url, json={"prompt": edited, "references": clip["references"]}).json()
    assert shown["auto_fix"] is None  # new words: no stale Undo left to offer (Flow-QA)
    assert editor.post(f"{url}/generate").status_code == 201


def test_reword_never_touches_the_spoken_words():
    from app.clip_prompts import reword

    prompt = ('Shot 1 | 0-2 s. Mom says no and Dad refuses. No one speaks.\n'
              'Shot 2 | 2-4 s. Mom says "Say it in 9:16, I refuse."')  # fmt: skip
    fixed, said = reword(prompt)
    assert fixed == ('Shot 1 | 0-2 s. Mom gestures no and Dad waves it off. No one speaks.\n'
                     'Shot 2 | 2-4 s. Mom says "Say it in 9:16, I refuse."')  # fmt: skip
    assert said == ['changed "says" to "gestures"', 'changed "refuses" to "waves it off"']


def test_an_edit_while_a_retry_waits_cancels_it_uncharged(app, db, editor, setup, clip):  # noqa: F811
    from app.credits import credits_used
    from app.models.projects import Project

    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    project = db.get(Project, setup["project"])
    before = credits_used(db, project)
    editor.post(f"{url}/generate")
    _work(app, db, Busy([]))
    retry = db.query(Job).filter(Job.auto.is_(True)).one()
    edited = clip["prompt"].replace("Close-up, push in.", "Close-up.")  # Flow-QA's case
    shown = editor.put(url, json={"prompt": edited, "references": clip["references"]}).json()
    assert shown["retrying"] is None  # at once, before the worker cancels it
    retry.input = {**retry.input, "wait_until": ""}
    db.commit()
    _work(app, db, FakeSeedance([_mp4("red")]))
    db.refresh(retry)
    assert retry.status == "cancelled" and retry.provider_ref is None  # never sent
    (shown,) = editor.get(f"/projects/{setup['project']}/clips").json()
    assert shown["takes"] == [] and shown["retrying"] is None
    assert credits_used(db, project) == before


def test_reword_takes_out_words_drawn_on_screen_but_never_the_spoken_ones():
    from app.clip_prompts import reword

    prompt = ('Shot 1 | 0-2 s. Mom holds the bag up, big text "SALE" pops, captions below. '
              'No one speaks.\nShot 2 | 2-4 s. Mom says "Add captions, darling."')  # fmt: skip
    fixed, said = reword(prompt)
    assert "captions below" not in fixed and 'Mom says "Add captions, darling."' in fixed
    assert 'removed "captions"' in said
    assert reword(fixed) == (fixed, [])  # fixed once: nothing more to do


def test_a_shot_that_is_only_drawn_words_stays_and_gets_advice(app, db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    lines = clip["prompt"].splitlines()
    keep = next(i for i, x in enumerate(lines) if x.startswith("Keep: "))
    words = "\n".join([*lines[:keep], "Shot 3 | 5-6 s. Title card: SALE.",
                        *lines[keep:]])  # a wordless shot that is only drawn words  # fmt: skip
    body = {"prompt": words, "references": clip["references"]}
    shown = editor.put(url, json=body).json()
    assert "Title card: SALE." in shown["prompt"]  # never emptied (#890)
    assert any(p.startswith("Advice: ") and "only words on screen" in p for p in shown["problems"])
