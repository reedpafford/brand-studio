"""What a revision makes again (F15): a run after a delivery whose story stands is priced, and
its progress shown, as only that (`estimate`, `run_progress`)."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts
from app.models.clips import ProjectClip
from app.models.projects import Project

CLIPS = re.compile(r"\bclips?\s+(\d+[a-z]?(?:(?:\s*(?:,|&|-|–|\band\b|\bto\b)\s*)+\d+[a-z]?)*)",
                   re.I)  # fmt: skip
SPAN = re.compile(r"(\d+)\s*(?:-|–|\bto\b)\s*(\d+)")  # "3-5", "3 to 5": 3, 4 and 5
LOOK_MOVES = ("make_looks", "change_look")  # paid; an outfit is free, but its clips change too


def named(text: str) -> set[str]:
    """The clips a note names: "clip 3", "clips 3, 5 and 6", "clips 3-5", "clips 3 to 5"."""

    def span(m: re.Match) -> str:
        return " ".join(map(str, range(int(m[1]), min(int(m[2]), int(m[1]) + 99) + 1)))

    return {f"c{n}" for found in CLIPS.findall(text)
            for n in re.findall(r"\d+[a-z]?", SPAN.sub(span, found))}  # fmt: skip


def revision(db: Session, video, ended: bool = False) -> tuple[list[ProjectClip], int] | None:
    """What a revision makes (`director.REVISION`: a run after a delivery whose story stands;
    F15: Skeleton 261's card said about $15.91, one clip again cost $2.81): the clips it makes
    again, those its notes name ("clips 3, 5 and 6"), else those showing someone whose look
    it changes, as Cast lists them; those its moves ask for (made, or waiting for Make it), out
    of date or with no take yet; and how many looks, those its moves make and each role still
    without one. Its song, plan and the clips it keeps are made already. None for any other
    run, or with none yet; once it ended, unless `ended` (its own record): Make it again
    starts a new run (QA on #1481: a stopped revision's button said its $2.38, the run it
    started $6.08)."""
    from app import director
    from app.sheets import roles_needing_look, roles_without_a_look
    from app.video_settings import out_of_date

    rows = director.all_turns(db, video.id) if video is not None and video.id else []
    run = (rows[-1].input.get(director.RUN) or {}) if rows else {}
    if not run.get(director.REVISION) or director._own_story(db, run, video.id):
        return None
    if not ended and director.over(db, run["id"], video.id):
        return None
    moves = [t.output or {} for t in director.turns(db, video)
             if not (t.input.get("result") or "").startswith("Refused")]  # fmt: skip
    looks = {(m.get("look") or {}).get("name") for m in moves if m.get("tool") in LOOK_MOVES}
    looks |= {*roles_without_a_look(db, video), *roles_needing_look(db, video)}
    looks -= {None, ""}
    bd = clip_prompts.newest(db, video)
    ids = named(" ".join(m["text"] for m in director.chat(video, run["id"])))
    if not ids:  # "Give Maya a red coat": the clips she's in
        dressed = {(m.get("look") or {}).get("name") for m in moves if m.get("tool") == "outfit"}
        ids = _showing(db, video, bd, looks | dressed)
    ids |= {m["clip_id"] for m in moves if m.get("tool") == "make_take" and m.get("clip_id")}
    of = {s: c["id"] for c in (bd.data.get("clips", []) if bd else []) for s in c["shot_ids"]}
    ids |= {of.get(r.get("shot_id")) for m in moves if m.get("tool") == "redraw_still"
            for r in m.get("redraws") or [m]}  # fmt: skip
    stale = {c.id for c in out_of_date(db, video)[1]}
    plan = bd.id if bd else None
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == video.id,
                                                ProjectClip.breakdown_id == plan))  # fmt: skip
    clips = [c for c in rows if c.clip_id in ids or c.id in stale or not c.picked_take_id]
    return clips, len(looks)


def _showing(db: Session, video: Project, bd, names: set) -> set[str]:
    """The clips whose shots show these people, as the Cast tab lists them (their role, its
    look, or a look of that name)."""
    from app.cast_roles import picked, video_slots
    from app.models.library import LibraryItem

    want = {(n or "").strip().lower() for n in names} - {""}
    if not want or bd is None:
        return set()
    shots = {s["id"]: s for sc in bd.data.get("scenes", []) for s in sc.get("shots", [])}
    refs = {r for s in shots.values() for r in s.get("character_ids", [])}
    who = {r for r in refs if r.startswith("char:") and (item := db.get(LibraryItem, int(r[5:])))
           and item.name.strip().lower() in want}  # fmt: skip
    for slot in video_slots(db, video):
        if slot.role.strip().lower() in want:
            who |= {f"slot:{slot.id}", f"char:{picked(video, slot)}",
                    f"char:{(video.slot_looks or {}).get(str(slot.id))}"}  # fmt: skip
    return {
        c["id"]
        for c in bd.data.get("clips", [])
        if any(who & set(shots.get(i, {}).get("character_ids", [])) for i in c["shot_ids"])
    }
