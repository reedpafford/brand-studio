"""best_take(clip): the take to pick, from what its checks found (the director's hand fix)."""

from app.best_take import best_take
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def _takes(app, db, editor, setup, clip, n):  # noqa: F811
    """`n` takes of the clip, with no checks yet (checks off while they're made)."""
    for _ in range(n):
        editor.post(f"/projects/{setup['project']}/clips/{clip['id']}/generate")
        _work(app, db, FakeSeedance([_mp4("red")]))
    row = db.get(ProjectClip, clip["id"])
    return row, list(db.query(ClipTake).filter_by(clip_id=row.id).order_by(ClipTake.number))


def _checked(db, row, take, status="done", findings=0, dismissed=0, target="take"):
    db.add(ItemCheck(project_id=row.project_id, target=target, target_id=take.id, status=status,
                     findings=[{"kind": "face", "role": "", "text": "x", "change_note": "y"}]
                     * findings, dismissed=[{"index": i} for i in range(dismissed)]))  # fmt: skip
    db.commit()


def test_a_clean_take_beats_a_newer_flagged_one(app, db, editor, setup, clip):  # noqa: F811
    row, (old, new) = _takes(app, db, editor, setup, clip, 2)
    _checked(db, row, old)
    _checked(db, row, new, findings=1)
    assert best_take(db, row).id == old.id


def test_among_flagged_takes_the_fewest_open_findings_wins(app, db, editor, setup, clip):  # noqa: F811
    row, (a, b, c) = _takes(app, db, editor, setup, clip, 3)
    _checked(db, row, a, findings=2)
    _checked(db, row, b, findings=3, dismissed=2)  # Looks fine twice: one still open
    _checked(db, row, c, findings=2)
    _checked(db, row, c, findings=1, target="words")  # its words count too
    assert best_take(db, row).id == b.id


def test_newest_wins_a_tie_and_checking_ranks_after_clean(app, db, editor, setup, clip):  # noqa: F811
    row, (a, b, c) = _takes(app, db, editor, setup, clip, 3)
    for t in (a, b):
        _checked(db, row, t)
    _checked(db, row, c, status="checking")
    assert best_take(db, row).id == b.id


def test_another_looks_take_is_never_chosen_and_none_is_none(app, db, editor, setup, clip):  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    assert best_take(db, row) is None
    row, (old, new) = _takes(app, db, editor, setup, clip, 2)
    _checked(db, row, old)
    _checked(db, row, new, findings=1)
    old.look = "anime"  # made before the video's look changed
    db.commit()
    assert best_take(db, row).id == new.id  # flagged, but the only current take
