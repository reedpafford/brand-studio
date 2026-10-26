"""Review the breakdown (reel-import.md §4): the reel's shots for the screen, read only."""

from app.models.script_library import Script
from tests.test_script_library import SCRIPT, _make


def _shot(n, start, end, **extra):
    return {"n": n, "start": start, "end": end, "framing": "wide", "camera": "static",
            "action": f"shot {n}", "emotion": "", **extra}  # fmt: skip


def test_the_review_shows_each_shot_dropped_live_action_and_montages(owner, db):
    sid = _make(owner, text=SCRIPT)["id"]
    url = f"/scripts/{sid}/import/breakdown"
    assert owner.get(url).status_code == 404  # not from a reel
    script = db.get(Script, sid)
    script.reel = {"video_file_id": None, "seconds": 12.0}
    db.commit()
    assert owner.get(url).json()["detail"] == "The reel hasn't been read yet."
    quick = [_shot(n, 2 + (n - 3) * 0.5, 2 + (n - 2) * 0.5) for n in range(3, 9)]  # 6 × 0.5 s
    script.reference_breakdown = {
        "logline": "A groom is dumped at the altar and wins.",
        "duration_seconds": 12.0,
        "hook": {"seconds": 2.0, "mechanic": "Cold open mid-refusal"},
        "beats": [],
        "shots": [
            _shot(1, 0, 1, speaker="GROOM", line="I do."),
            _shot(2, 1, 2, speaker="BRIDE", line="HELL NO!"),
            *quick,
            _shot(9, 5, 12, style="live action", line="Follow for more"),
        ],
    }
    db.commit()
    got = owner.get(url).json()  # free: nothing is charged
    assert (got["logline"], got["hook_seconds"], got["hook"]) == (
        "A groom is dumped at the altar and wins.", 2.0, "Cold open mid-refusal"
    )  # fmt: skip
    assert len(got["shots"]) == 9 and got["shots"][1]["line"] == "HELL NO!"
    assert [s["n"] for s in got["shots"] if s["dropped"]] == [9]
    assert (got["dropped"], got["lines"]) == (1, 2)  # the live-action line isn't counted
    assert got["montages"] == [{"first": 3, "last": 8, "seconds": 3.0}]
