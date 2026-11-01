"""best_take(clip): the take to pick, from what its checks found (the director's hand fix)."""

from sqlalchemy.orm.attributes import flag_modified

from app import clip_prompts
from app.best_take import best_take
from app.models.breakdowns import BreakdownVersion
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
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


def test_a_clip_for_an_older_breakdown_has_no_best_take(app, db, editor, setup, clip):  # noqa: F811
    row, (take,) = _takes(app, db, editor, setup, clip, 1)
    _checked(db, row, take)
    was = db.get(BreakdownVersion, row.breakdown_id)
    db.add(BreakdownVersion(project_id=was.project_id, script_version=was.script_version,
                            source=was.source, data=was.data))  # fmt: skip
    db.commit()
    assert clip_prompts.is_stale(db, row, db.query(BreakdownVersion).all()[-1])
    assert best_take(db, row) is None  # its prompt needs rewriting first


def _sent(db, take, files):
    job = db.get(Job, take.job_id)
    job.input = {**job.input, "files": {"reference_images": files}}
    flag_modified(job, "input")


def test_out_of_date_takes_arent_chosen(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    row, (a, sheet, still, prompt, picked) = _takes(app, db, editor, setup, clip, 5)
    for t in (a, sheet, still, prompt, picked):
        _checked(db, row, t)
    now = sorted(db.get(Job, a.job_id).input["files"]["reference_images"])  # Mom's sheet
    frame = a.file_id  # a stored picture, standing in for the frame's Preferred still
    assets = clip_prompts.assets
    monkeypatch.setattr(clip_prompts, "assets", lambda db, p: {
        **assets(db, p), "frame:c1": ("Frame", "image", [frame])})  # fmt: skip
    row.references = [*row.references, {"kind": "image", "id": "frame:c1", "role": "x"}]
    for t in (a, prompt, picked):
        _sent(db, t, [*now, frame])
    _sent(db, sheet, [frame])  # Mom's sheet changed since it was made
    _sent(db, still, now)  # made from an earlier still
    row.prompt_history = [{"v": 2}, {"v": 1}]
    for t in (a, sheet, still, picked):
        t.made_with = {**(t.made_with or {}), "prompt_version": 2}
    prompt.made_with = {**(prompt.made_with or {}), "prompt_version": 1}  # Go back to this
    row.problems, row.kept = [clip_prompts.OLDER_PROMPT], [clip_prompts.OLDER_PROMPT]
    db.commit()
    known = clip_prompts.assets(db, db.get(Project, row.project_id))
    older = [(bool(clip_prompts.older_take(db, known, row, t)),
              clip_prompts.older_still(db, known, row, t), clip_prompts.older_prompt(db, row, t))
             for t in (a, sheet, still, prompt)]  # fmt: skip
    assert older == [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ]  # each made out of date one way
    assert best_take(db, row).id == picked.id  # the picked one: a person kept it anyway
    row.kept = []
    db.commit()
    assert best_take(db, row).id == a.id  # the newest current take
