"""Song takes on a song script's version: make 2, their states, Try again, Preferred and
remove, all on the free stand-ins (no paid calls)."""

import pytest

from app import music, song_takes
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.providers import get_providers
from app.worker import run_once
from tests.helpers import assert_no_dollars
from tests.test_music import LYRICS


@pytest.fixture
def song(app, owner):
    app.state.settings.fake_providers = True
    brand = owner.get("/brands").json()[0]["id"]
    script = owner.post(
        "/scripts", json={"brand_id": brand, "title": "Paws", "kind": "song", "text": LYRICS}
    ).json()
    assert script["kind"] == "song"
    return f"/scripts/{script['id']}/drafts/0"


def _style(client, url, style):
    lyrics = client.get(url.rsplit("/drafts", 1)[0]).json()["versions"][0]["text"]
    r = client.put(url, json={"text": lyrics, "style_line": style})
    assert r.status_code == 200, r.text


def _work(app, db, ticks=4):
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)


def test_two_takes_are_made_timed_and_one_is_preferred(app, db, owner, song):
    _style(owner, song, "pop, female lead, 120 BPM")
    made = owner.post(f"{song}/songs", json={})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["songs_on"] and body["estimate_credits"] == 1  # one request (2 songs)
    assert [(t["number"], t["status"]) for t in body["takes"]] == [(1, "making"), (2, "making")]
    _work(app, db)
    takes = owner.get(f"{song}/songs").json()["takes"]
    assert [(t["status"], t["preferred"]) for t in takes] == [("ready", True), ("ready", False)]
    assert takes[0]["seconds"] > 20 and len(takes[0]["peaks"]) == 200
    assert not takes[0]["out_of_date"]

    picked = owner.post(f"/songs/{takes[1]['id']}/preferred").json()
    assert picked["take"]["preferred"] and picked["was_preferred_id"] == takes[0]["id"]
    owner.post(f"/songs/{takes[0]['id']}/preferred")  # Undo
    assert [t["preferred"] for t in owner.get(f"{song}/songs").json()["takes"]] == [True, False]

    _style(owner, song, "rock, male lead")  # new words or style: the takes are out of date
    assert all(t["out_of_date"] for t in owner.get(f"{song}/songs").json()["takes"])
    r = owner.post(f"/songs/{takes[1]['id']}/preferred")
    assert (r.status_code, r.json()["detail"]) == (409, song_takes.OLDER_WORDS)


def test_a_skipped_or_repeated_line_is_advice_never_a_block(app, db, owner, song):
    _style(owner, song, "pop fake:drop-line")
    owner.post(f"{song}/songs", json={})
    _style(owner, song, "pop fake:repeat-line")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    dropped, _, repeated, _ = owner.get(f"{song}/songs").json()["takes"]
    assert dropped["status"] == "ready" and dropped["advice"] == [
        "Timing guessed: line 4 (“Iron Paws, my best ally”) wasn't heard in this take."
    ]
    assert repeated["advice"] == ["Line 4 (“Iron Paws, my best ally”) is sung 2 times."]
    # The first take sings the older style line, so the current one became Preferred.
    assert (dropped["preferred"], repeated["preferred"]) == (False, True)


def test_a_failed_take_says_why_and_try_again_makes_it(app, db, owner, song):
    _style(owner, song, "pop fake:refuse")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    takes = owner.get(f"{song}/songs").json()["takes"]
    assert [(t["status"], t["failed_reason"], t["retry_helps"]) for t in takes] == [
        ("failed", music.REFUSED, True)
    ] * 2  # fmt: skip
    assert takes[0]["retry_credits"] == 1  # a new request
    take = takes[0]
    assert "E005" not in owner.get(f"{song}/songs").text  # the raw reason is owner-only
    _style(owner, song, "pop")  # the words are changed, as the reason says
    again = owner.post(f"/songs/{take['id']}/try-again")
    assert again.status_code == 200 and again.json()["status"] == "making"
    _work(app, db)
    takes = owner.get(f"{song}/songs").json()["takes"]
    assert [(t["status"], t["out_of_date"]) for t in takes] == [("ready", False)] * 2
    take = takes[0]
    assert take["preferred"]  # both of the request's takes came back on one Try again
    r = owner.post(f"/songs/{take['id']}/try-again")
    assert r.status_code == 409  # nothing failed: nothing to try again


def test_the_preferred_take_cant_be_removed_others_can_with_undo(app, db, owner, song):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    first, second = owner.get(f"{song}/songs").json()["takes"]
    r = owner.delete(f"/songs/{first['id']}")
    assert (r.status_code, r.json()["detail"]) == (409, song_takes.PREFERRED)
    assert owner.delete(f"/songs/{second['id']}").status_code == 204
    assert [t["id"] for t in owner.get(f"{song}/songs").json()["takes"]] == [first["id"]]
    assert owner.post(f"/songs/{second['id']}/restore").status_code == 200  # Undo
    assert len(owner.get(f"{song}/songs").json()["takes"]) == 2


def test_lyrics_past_sunos_limit_are_refused_when_saved(owner, song):
    r = owner.put(song, json={"text": "la " * 1700})
    assert (r.status_code, r.json()["detail"]) == (422, music.TOO_LONG)
    r = owner.put(song, json={"text": LYRICS, "style_line": "x" * 900})
    assert (r.status_code, r.json()["detail"]) == (422, music.STYLE_TOO_LONG)


def test_a_song_needs_lyrics_and_a_song_script(app, owner, song):
    owner.put(song, json={"text": "[Verse]", "style_line": "pop"})
    r = owner.post(f"{song}/songs", json={})
    assert (r.status_code, r.json()["detail"]) == (422, music.NO_LYRICS)
    brand = owner.get("/brands").json()[0]["id"]
    story = owner.post("/scripts", json={"brand_id": brand, "title": "S", "text": "HI: there"})
    assert story.json()["kind"] == "story"
    r = owner.post(f"/scripts/{story.json()['id']}/drafts/0/songs", json={})
    assert r.status_code == 409 and "isn't a song" in r.json()["detail"]


def test_songs_off_here_says_so_instead_of_failing(app, owner, song):
    app.state.settings.fake_providers = False  # no Suno access yet: no songs on a real server
    assert owner.get(f"{song}/songs").json()["songs_on"] is False
    r = owner.post(f"{song}/songs", json={})
    assert (r.status_code, r.json()["detail"]) == (503, "Songs aren't switched on here.")


def test_editors_make_their_own_songs_in_credits_but_cant_touch_others(app, db, editor, song):
    assert editor.get(f"{song}/songs").status_code == 404  # not published: not theirs to see
    brand = editor.get("/brands").json()[0]["id"]
    mine = editor.post(
        "/scripts", json={"brand_id": brand, "title": "Mine", "kind": "song", "text": LYRICS}
    ).json()
    url = f"/scripts/{mine['id']}/drafts/0"
    _style(editor, url, "pop")
    made = editor.post(f"{url}/songs", json={})
    assert made.status_code == 201 and made.json()["estimate_credits"] == 1
    _work(app, db)
    assert_no_dollars(editor, [f"{url}/songs"])


def test_a_timing_that_cant_be_heard_can_be_spread_evenly(app, db, owner, song, monkeypatch):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    providers = get_providers(app.state.settings, app.state.storage)

    def slow(path, lyrics):
        raise RuntimeError("Reading the sung words took too long.")

    monkeypatch.setattr(providers["local"], "hear_song", slow)
    for _ in range(4):
        run_once(db, providers, app.state.storage)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["retry_helps"]) == ("timing_failed", True)
    spread = owner.post(f"/songs/{take['id']}/spread-timing")
    assert spread.status_code == 200 and spread.json()["status"] == "timing"
    for _ in range(2):
        run_once(db, providers, app.state.storage)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert (take["status"], take["timing_guessed"], take["preferred"]) == ("ready", True, True)
    assert take["advice"] == [song_takes.GUESSED]


def _video(app, db, owner, editor, song):
    """A published song version with two finished takes, made into a video by the editor."""
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    base = song.rsplit("/drafts", 1)[0]
    owner.post(f"{song}/approve")
    owner.post(f"{base}/publish")
    made = editor.post(f"{song}/produce")
    assert made.status_code == 201, made.text
    video = f"/projects/{made.json()['project_id']}"
    _work(app, db)  # its plan (flows 1b), then the shots from it (stand-ins)
    _approve_plan(app, db, editor, video)
    return video


def _approve_plan(app, db, editor, video):
    """Approve the video's plan: the shots are made from it."""
    approved = editor.post(f"{video}/plan/approve")
    assert approved.status_code == 200, approved.text
    _work(app, db)


def test_a_video_starts_on_the_preferred_take_and_can_switch_with_undo(
    app, db, owner, editor, song
):
    video = _video(app, db, owner, editor, song)
    songs = editor.get(f"{video}/songs").json()
    first, second = songs["takes"]
    assert songs["song_take_id"] == first["id"] and first["preferred"]
    assert not first["in_video"]
    assert (
        editor.get(video).json()["song"] and editor.get(video).json()["song_take_id"] == first["id"]
    )
    switched = editor.put(f"{video}/song", json={"take_id": second["id"]}).json()
    assert switched == {"song_take_id": second["id"], "was_song_take_id": first["id"]}
    editor.put(f"{video}/song", json={"take_id": first["id"]})  # Undo
    assert editor.get(f"{video}/songs").json()["song_take_id"] == first["id"]
    # The script's takes stay as they are: the published script is final (rule 31).
    assert editor.post(f"/songs/{second['id']}/preferred").status_code in (403, 409)


def test_a_video_makes_its_own_takes_on_its_budget(app, db, owner, editor, song):
    video = _video(app, db, owner, editor, song)
    made = editor.post(f"{video}/songs", json={})
    assert made.status_code == 201, made.text
    _work(app, db)
    takes = editor.get(f"{video}/songs").json()["takes"]
    own = takes[-1]
    assert own["in_video"] and not any(t["preferred"] for t in takes[2:])  # videos use song
    assert len(takes) == 4 and own["status"] == "ready" and own["number"] == 2
    job = db.query(Job).filter(Job.kind == "music").order_by(Job.id.desc()).first()
    assert job.project_id == int(video.rsplit("/", 1)[1])  # charged to the video
    editor.put(f"{video}/song", json={"take_id": own["id"]})
    r = editor.delete(f"/songs/{own['id']}")
    assert (r.status_code, r.json()["detail"]) == (409, song_takes.IN_USE)
    editor.put(f"{video}/song", json={"take_id": takes[0]["id"]})
    assert editor.delete(f"/songs/{own['id']}").status_code == 204


def test_a_refused_take_in_a_video_doesnt_ask_to_change_final_lyrics(app, db, owner, editor, song):
    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:refuse"  # only to reach the refusal on the stand-in
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    own = editor.get(f"{video}/songs").json()["takes"][-1]
    assert (own["status"], own["failed_reason"]) == ("failed", music.REFUSED_IN_VIDEO)
    assert own["refused_for"] == "words"


def test_a_take_over_the_cap_offers_its_first_part_with_undo(app, db, owner, song):
    _style(owner, song, "pop fake:long=800")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    take = owner.get(f"{song}/songs").json()["takes"][0]
    assert take["status"] == "ready" and take["over_cap"] and not take["preferred"]
    assert take["fits_until"] == 14.25 and take["video_credits"] > 729
    r = owner.post(f"/songs/{take['id']}/preferred")
    assert r.status_code == 409 and "Press Use the first 0:14" in r.json()["detail"]
    trimmed = owner.post(f"/songs/{take['id']}/trim").json()
    assert (trimmed["trim_to"], trimmed["over_cap"]) == (14.25, False)
    assert owner.post(f"/songs/{take['id']}/preferred").status_code == 200
    whole = owner.delete(f"/songs/{take['id']}/trim").json()  # Undo
    assert (whole["trim_to"], whole["over_cap"], whole["preferred"]) == (None, True, False)
    base = song.rsplit("/drafts", 1)[0]
    owner.post(f"{song}/approve")
    r = owner.post(f"{base}/publish")  # nothing under the cap is Preferred: no publish
    assert r.status_code == 409 and r.json()["detail"].startswith("Make the song first")


def test_a_tag_change_doesnt_date_the_takes(app, db, owner, song):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    owner.put(song, json={"text": f"[Lip-sync]\n{LYRICS}", "style_line": "pop"})
    assert not any(t["out_of_date"] for t in owner.get(f"{song}/songs").json()["takes"])


def test_a_song_script_publishes_only_with_a_preferred_take(app, db, owner, song):
    base = song.rsplit("/drafts", 1)[0]
    _style(owner, song, "pop")
    owner.post(f"{song}/approve")
    r = owner.post(f"{base}/publish")
    assert r.status_code == 409 and r.json()["detail"].startswith("Make the song first")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    assert owner.post(f"{base}/publish").status_code == 200


@pytest.mark.parametrize(
    ("marker", "about"), [("fake:refuse", "words"), ("fake:copyright", "style")]
)
def test_a_refusal_says_whether_to_change_the_words_or_the_style(
    app, db, owner, song, marker, about
):
    _style(owner, song, f"pop {marker}")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    assert owner.get(f"{song}/songs").json()["takes"][0]["refused_for"] == about


def test_an_over_cap_take_becomes_the_videos_song_only_trimmed(app, db, owner, editor, song):
    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:long=800"  # only to make a long take on the stand-in
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    long = editor.get(f"{video}/songs").json()["takes"][-1]
    r = editor.put(f"{video}/song", json={"take_id": long["id"]})
    assert r.status_code == 409 and "Press Use the first 0:14" in r.json()["detail"]
    assert editor.post(f"/songs/{long['id']}/trim").json()["trim_to"] == 14.25
    assert editor.put(f"{video}/song", json={"take_id": long["id"]}).status_code == 200


def test_marking_a_section_for_lip_sync_doesnt_date_the_takes(app, db, owner, song):
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    marked = LYRICS.replace("[Chorus]", "[Chorus] [Lip-sync]")
    owner.put(song, json={"text": marked, "style_line": "pop"})
    assert not any(t["out_of_date"] for t in owner.get(f"{song}/songs").json()["takes"])


def test_lyrics_too_long_for_the_cap_say_how_many_lines_to_keep(app, owner, song):
    body = owner.get(f"{song}/songs").json()
    assert body["keep_lines"] is None and 0 < body["video_estimate_credits"] < 729
    long = "\n".join("la " * 10 for _ in range(160))  # about 800 s sung, under 5,000 chars
    assert owner.put(song, json={"text": long, "style_line": "pop"}).status_code == 200
    body = owner.get(f"{song}/songs").json()
    assert body["video_estimate_credits"] > 729 and 0 < body["keep_lines"] < 160


def test_a_reply_with_one_song_keeps_it_and_asks_again_free(app, db, owner, song):
    from app.models.jobs import Job

    _style(owner, song, "pop fake:one-song")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    kept, missing = owner.get(f"{song}/songs").json()["takes"]
    assert (kept["status"], missing["status"]) == ("ready", "failed")
    assert missing["failed_reason"] == music.MISSING
    assert missing["retry_credits"] == 0  # the request was paid for both songs
    assert owner.post(f"/songs/{missing['id']}/try-again").status_code == 200
    again = db.query(Job).filter(Job.kind == "music").order_by(Job.id.desc()).first()
    assert again.credits == 0  # the first request was charged for both songs
    _work(app, db)
    takes = owner.get(f"{song}/songs").json()["takes"]
    assert [t["id"] for t in takes] == [kept["id"], missing["id"]]
    assert takes[0]["file_id"] == kept["file_id"]  # the song that came stays
    # Short again on the free retry: the next Try again is charged (one free retry a request)
    again_missing = owner.get(f"{song}/songs").json()["takes"][1]
    assert (again_missing["status"], again_missing["retry_credits"]) == ("failed", 1)


def test_a_videos_own_take_can_be_removed_unless_its_the_song(app, db, owner, editor, song):
    video = _video(app, db, owner, editor, song)
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    first_own = editor.get(f"{video}/songs").json()["takes"][2]
    assert editor.delete(f"/songs/{first_own['id']}").status_code == 204  # no dead end
    r = editor.post(f"/songs/{first_own['id']}/preferred")
    assert r.status_code == 409 and "Use in this video" in r.json()["detail"]


def test_take_cards_and_the_version_show_one_price(app, db, owner, song):
    """A take's video price counts the roles not cast yet, as the version's does, and the
    Song version's price is its Preferred take's video."""
    _style(owner, song, "pop, female lead, 120 BPM")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    base = song.rsplit("/drafts", 1)[0]
    alone = owner.get(f"{song}/songs").json()["takes"][0]["video_credits"]
    owner.post(f"{base}/cast", json={"role": "Singer"})
    take = owner.get(f"{song}/songs").json()["takes"][0]
    version = owner.get(base).json()["versions"][0]
    assert take["video_credits"] > alone
    assert version["estimate_credits"] == pytest.approx(take["video_credits"])


def test_a_song_videos_shots_and_clips_last_as_long_as_the_song(app, db, owner, editor, song):
    """V2, V6: the song is the clock. Next-Layout saw "1 clip · 14 s" for a 0:24 song (the
    plan counted spoken words). Each shot now lasts its time in the song, each clip its
    shots' span rounded up, the clips cover the whole song, and the bar prices those."""
    import math

    from sqlalchemy import select

    from app.models.breakdowns import BreakdownVersion
    from app.models.projects import Project

    video = _video(app, db, owner, editor, song)
    pid = int(video.rsplit("/", 1)[1])
    row = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                     .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    times, end = row.data["song"]["shots"], 0.0
    for shot in (s for sc in row.data["scenes"] for s in sc["shots"]):
        t = times[shot["id"]]
        assert shot["seconds"] == pytest.approx(t["end"] - t["start"], abs=0.01)
        end = max(end, t["end"])
    spans = []
    for clip in row.data["clips"]:
        mine = [times[s] for s in clip["shot_ids"]]
        span = max(t["end"] for t in mine) - min(t["start"] for t in mine)
        assert clip["seconds"] == math.ceil(span - 0.01)  # rounded up, never short
        spans.append(clip["seconds"])
    assert sum(spans) >= end and db.get(Project, pid).breakdown_seconds == sum(spans)
    stages = {s["stage"]: s for s in editor.get(f"{video}/estimate").json()["stages"]}
    assert stages["clips"]["credits"] == pytest.approx(sum(spans))  # 1 credit a second


def test_a_song_on_a_short_model_is_split_into_clips_it_can_make(app, db, owner, song):
    """The stand-in cuts a song's clips at the video model's longest by the song's own
    times, so a 0:24 song on Seedance 2.0 (15 s a clip) is never one clip it can't make."""
    from sqlalchemy import select

    from app.models.breakdowns import BreakdownVersion

    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    owner.post(f"{song}/approve")
    owner.post(f"{song.rsplit('/drafts', 1)[0]}/publish")
    made = owner.post(f"{song}/produce", json={"video_model": "seedance-2.0"}).json()
    _work(app, db)  # the plan
    _approve_plan(app, db, owner, f"/projects/{made['project_id']}")
    mine = BreakdownVersion.project_id == made["project_id"]
    row = db.scalars(
        select(BreakdownVersion).where(mine).order_by(BreakdownVersion.id.desc())
    ).first()
    seconds = [c["seconds"] for c in row.data["clips"]]
    end = max(t["end"] for t in row.data["song"]["shots"].values())
    assert len(seconds) >= 2 and max(seconds) <= 15 and sum(seconds) >= end
    assert not [p for p in row.problems if "is outside" in p]  # no clip over the limit


def test_a_song_videos_quote_card_and_bar_are_one_figure(app, db, owner, song):
    """Rule 32 (up to a look per role that will need one, and the plan call the press charges)
    and the song's own length: Make this version's quote and the take card are one figure,
    the plan's charge plus the made video's cost bar, on a song video with a role not cast
    yet."""
    from app import video_settings as vs
    from app.models.projects import Project

    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    base = song.rsplit("/drafts", 1)[0]
    owner.post(f"{base}/cast", json={"role": "Singer"})  # not cast yet: needs a look
    owner.post(f"{song}/approve")
    owner.post(f"{base}/publish")
    quote = owner.post(f"{song}/estimate").json()["credits"]
    card = owner.get(f"{song}/songs").json()["takes"][0]["video_credits"]
    made = owner.post(f"{song}/produce").json()["project_id"]
    plan = float(sum(j.credits for j in db.query(Job).filter_by(project_id=made)))
    assert plan == 3  # Make this version charged the plan call at once
    bar = owner.get(f"/projects/{made}/estimate").json()["remaining_credits"]
    to_finish = float(vs.to_finish(db, db.get(Project, made)))
    assert quote == pytest.approx(card)  # the card and the quote: one figure
    assert quote == pytest.approx(plan + bar, abs=0.01)  # what the press and the rest cost
    assert to_finish == pytest.approx(bar, abs=0.01)


def test_a_clip_over_the_video_models_longest_is_flagged_refused_and_split(app, db, owner, song):
    """QA #1013: the 0:24 song is one 25 s clip on Seedance 2.5 (30 s), fine; switched to 2.0
    (15 s) the plan says so with its Split fix, a take is refused before any charge, and
    Split the clip makes clips 2.0 can make."""
    from sqlalchemy import func, select

    from app.models.breakdowns import BreakdownVersion
    from app.models.clips import ProjectClip

    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    owner.post(f"{song}/approve")
    owner.post(f"{song.rsplit('/drafts', 1)[0]}/publish")
    made = owner.post(f"{song}/produce", json={"video_model": "seedance-2.5"}).json()
    video = f"/projects/{made['project_id']}"
    _work(app, db)
    _approve_plan(app, db, owner, video)
    long = [c for c in owner.get(f"{video}/breakdown").json()["breakdown"]["clips"]
            if c["seconds"] > 15]  # fmt: skip
    assert long and not [p for p in owner.get(f"{video}/breakdown").json()["problems"]
                         if "is outside" in p]  # fmt: skip
    owner.post(f"{video}/clips/prompts")
    _work(app, db)
    switched = owner.post(f"{video}/settings", json={"video_model": "seedance-2.0"})
    assert switched.status_code == 200, switched.text
    plan = owner.get(f"{video}/breakdown").json()
    said = f"clip {long[0]['id']}: {long[0]['seconds']} s is outside 4–15 s"
    assert said in plan["problems"]
    assert {"problem": said, "kind": "split_clip", "label": "Split the clip"} in plan["fixes"]
    row = db.scalars(select(ProjectClip).where(ProjectClip.seconds > 15)).first()
    spent = db.scalar(select(func.coalesce(func.sum(Job.credits), 0)))
    refused = owner.post(f"{video}/clips/{row.id}/generate")
    assert refused.status_code == 409 and "at most 15 s" in refused.json()["detail"]
    assert db.scalar(select(func.coalesce(func.sum(Job.credits), 0))) == spent  # no charge
    fixed = owner.post(f"{video}/breakdown/fix", json={"problems": [said]})
    assert fixed.status_code == 200, fixed.text
    _work(app, db)
    assert db.scalar(select(func.coalesce(func.sum(Job.credits), 0))) == spent  # free (QA-3)
    newest = db.scalars(select(BreakdownVersion).order_by(BreakdownVersion.id.desc())).first()
    assert max(c["seconds"] for c in newest.data["clips"]) <= 15
    from app import clip_prompts

    project = db.get(Project, made["project_id"])  # c1's shots changed: written again too
    assert clip_prompts.to_rewrite(db, project) == [c["id"] for c in newest.data["clips"]]
    stages = {s["stage"]: s for s in owner.get(f"{video}/estimate").json()["stages"]}
    assert not stages["clip_prompts"]["done"] and stages["clip_prompts"]["credits"] > 0
    assert not stages["clips"]["done"]  # both new clips' takes are still to make
    assert f"{sum(c['seconds'] for c in newest.data['clips'])} s" in stages["clips"]["note"]
    assert not [p for p in fixed.json()["problems"] if "is outside" in p]


def test_split_is_offered_only_for_a_clip_of_more_than_one_shot():
    """Flow-QA #1013: one over-long shot can't be split between shots, so no Split button."""
    from app import breakdown_fix

    said = "clip c1: 20 s is outside 4–15 s"
    two = {"clips": [{"id": "c1", "shot_ids": ["1.1", "1.2"]}]}
    one = {"clips": [{"id": "c1", "shot_ids": ["1.1"]}]}
    assert [f["kind"] for f in breakdown_fix.fixes([said], two)] == ["split_clip"]
    assert breakdown_fix.fixes([said], one) == []
