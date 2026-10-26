"""Clip takes (mocked Replicate, no paid calls), approval and the free stitch (real ffmpeg)."""

import json
import subprocess

import httpx2 as httpx
import pytest

from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import _usd_keys, assert_hidden, assert_no_dollars, with_sheet
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
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(bd))
    editor.post(f"/projects/{setup['project']}/clips/prompts")
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], _prompt())))
    return editor.get(f"/projects/{setup['project']}/clips").json()[0]


def _work(app, db, fake):
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(2):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)


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
    assert sent["prompt"] == clip["prompt"] and sent["aspect_ratio"] == "9:16"
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
