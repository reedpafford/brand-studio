"""The delivery note (v6 piece D: boards S3-09, S3-10, S3-12, P-08), built when the director
delivers and kept on its deliver turn, so a later run never rewrites it. The director writes
what it made, what remains uncertain and what it needs from you (its last turn:
DirectorTurn's `made`, `unsure` and `needs`); the server adds what it watched and redid, each
at its time in the cut (the takes it made again and its free fixes), what it knows is still
open (`open_items`), the run's real cost and the cut's number. "Ready to post" is said only
when nothing is open."""

import math
import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import watch_report
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.run_progress import RUN, _found, _model, dollars, runs, said, spent, watched

NOTHING = "Nothing. It’s ready to post."  # only when nothing is open (`open_items`)
LOOK_FIRST = "Nothing yet, but look at what remains uncertain before you post it."
FIXES = ("mute", "splice_word", "pick_take")  # the free fixes its rows name


def note(db: Session, project: Project, job: Job, decision: dict) -> dict:
    """The note for the run `job` delivers: {made, redid [{at, clip, text}], unsure, needs,
    spent, up_to, cut, seconds, clips}: money as charged, in credits; `shown` says it in dollars
    to the owner only (any teammate can read a job's output)."""
    turns = runs(db, project)[job.input[RUN]["id"]]
    cut = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                    .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip
    number = cut.number if cut else 0  # Cut N as the switch and the editor name it
    spans = _spans(db, cut)
    credits, up_to = spent(db, project)  # the whole video's, at this cut (board S3-12)
    rows = (_remade(db, project, spans, turns) + _fixed(db, project, spans, turns)
            + _host_rows(db, project, turns[0].created_at))  # fmt: skip
    return {"made": said(decision.get("made") or decision.get("why") or ""),
            "open": open_items(db, project, spans, decision.get("needs") or ""),
            "redid": sorted(rows, key=lambda r: r["at"]),
            "unsure": " ".join(x for x in (said(decision.get("unsure") or ""),
                                           watch_report.doubts(db, project)) if x),
            "needs": said(decision.get("needs") or ""),
            "spent": float(credits), "up_to": float(up_to),
            "cut": number, "clips": len(spans),
            "seconds": round(sum(s["seconds"] for s in spans), 1)}  # fmt: skip


def open_items(db: Session, project: Project, spans: list[dict], asked: str = "") -> list[str]:
    """What the server knows is still open when the director delivers, said plainly (Reed, 4
    Nov: a cut that exists isn't ready to post): a cut not watched; each finding of the watch
    of this cut (kept, or not fixed), but those the note already asks about (`asked`); each
    take in the cut not checked, or with what its checks found (not what was muted or spliced
    free); and each step waiting for the owner."""
    from app import item_checks
    from app.credits import WAIT_OK
    from app.director import _item
    from app.models.jobs import JobStatus
    from app.watch_cut import state

    out = []
    watch = state(db, project)
    if not (watch.get("state") == "done" and watch.get("current")):
        failed = watch.get("state") == "failed" and watch.get("current")
        out.append("The watch of the cut failed, so the cut wasn't watched." if failed
                   else "The cut wasn't watched.")  # fmt: skip
    where = {s["row"].clip_id: _clip(s["row"]) for s in spans}
    takes = {s["row"].clip_id: s["take"] for s in spans}
    for f in watch.get("findings") or [] if watch.get("current") else []:
        says = said(f.get("says") or "").rstrip(".")
        if not says or says.lower() in said(asked).lower() or _watch_fixed(f, takes):
            continue  # asked of the owner in the note, or fixed for free since (a mute, a pick)
        head = f"{where[f['clip_id']]}: " if f.get("clip_id") in where else ""
        done = "Kept as it is." if f.get("fix") == "keep" else "Not fixed."
        out.append(f"{head}{says}. {done}")
    if spans and not item_checks.on():  # checks are off on this site: said once
        out.append("The takes weren't checked one by one.")
    ids = [s["take"].id for s in spans]
    checks = {k: item_checks.latest(db, k, ids) for k in ("take", "words")}
    for s in spans:
        take, n = s["take"], _clip(s["row"])
        if (take.made_with or {}).get("talker"):
            continue  # cut from the talker's take: watched as the host's piece, below
        for k in ("take", "words"):
            for f in _found(checks[k].get(take.id)):
                if f.get("verified", True) and not _fixed_free(db, take, f):  # doubts: unsure
                    out.append(f"{n}: {said(f['text']).rstrip('.')}. Kept as it is.")
        mine = [checks[k].get(take.id) for k in ("take", "words")]
        if item_checks.on() and (mine[0] is None or any(c and c.status != "done" for c in mine)):
            out.append(f"{n}'s take wasn't checked.")  # none, failed, skipped or never finished
    out += _host_open(db, project)
    held = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.status == JobStatus.needs_owner_approval))  # fmt: skip
    for j in held:
        why = (j.input.get("held") or "").removeprefix(WAIT_OK).rstrip(".")
        line = f"{_item(db, j)} is waiting for the owner's OK" + (f": {why}." if why else ".")
        if line not in out:
            out.append(line)
    return out


def _host_open(db: Session, project: Project) -> list[str]:
    """A presenter's host pieces in use (not an earlier narration's): each one not watched,
    or with what its watch found and confirmed (its doubts are in "What remains uncertain")."""
    from app import host, item_checks

    rows = [r for r in host.rows(db, project) if r.number and r.file_id]
    checks = item_checks.latest(db, "piece", [r.id for r in rows])
    out = []
    for r in rows:
        who = f"The host's piece {r.number}"
        check = checks.get(r.id)
        for f in _found(check):
            if f.get("verified", True):
                out.append(f"{who}: {said(f['text']).rstrip('.')}. Kept as it is.")
        if item_checks.on() and (check is None or check.status != "done"):
            out.append(f"{who} wasn't checked.")
    return out


def _host_rows(db: Session, project: Project, since) -> list[dict]:
    """The host's pieces the watch made again this run, as rows of "What I watched and
    redid", at their place on the narration's clock: from the remakes themselves, since a
    remade piece's own watch replaces the one that asked for it."""
    from app import host, host_watch
    from app.models.jobs import JobStatus

    rows = {r.id: r for r in host.rows(db, project)}
    made = db.scalars(select(Job).where(Job.project_id == project.id, Job.created_at >= since,
                                        Job.status == JobStatus.succeeded)
                      .order_by(Job.id))  # fmt: skip
    out = []
    for j in made:
        row = rows.get(j.input.get(host_watch.REDO))
        if row is None:
            continue
        fix = (j.input.get(host_watch.NOTE) or "").strip().rstrip(".")
        out.append({"at": round(row.start, 1), "clip": "host",
                    "text": f"The host's piece {row.number}: made again"
                            + (f" with “{said(fix)}”." if fix else ".")})  # fmt: skip
    return out


def _watch_fixed(f: dict, takes: dict) -> bool:
    """A watch finding fixed without a new cut being needed: its stretch muted, or the take
    it pointed to is the one in the cut."""
    from app import take_mute

    take = takes.get(f.get("clip_id"))
    if take is None:
        return False
    if f.get("fix") == "mute" and f.get("mute"):
        span = [round(float(x), 2) for x in f["mute"]]
        return span in [[round(x, 2) for x in m] for m in take_mute.spans(take)]
    return f.get("fix") == "pick" and f.get("take_id") == take.id


def _fixed_free(db: Session, take: ClipTake, f: dict) -> bool:
    """A check's finding already fixed for free: its stretch muted, or a brand name heard
    wrong when every wrong copy of it in the take has a clean one spliced in."""
    from app import take_mute, word_splice

    if f.get("span") and list(f["span"]) in [list(x) for x in take_mute.spans(take)]:
        return True
    done = word_splice.spliced(take)
    if f.get("kind") != "name" or not done:
        return False
    return all(any(x.get("at") == w["at"] for x in done) for w in word_splice.wrong(db, take))


def _spans(db: Session, cut: FinalVideo | None) -> list[dict]:
    """Each clip of the cut in order: {row, take, start, seconds}."""
    takes = {t.id: t for t in db.scalars(select(ClipTake).where(
        ClipTake.id.in_(cut.take_ids)))} if cut else {}  # fmt: skip
    rows = {r.id: r for r in db.scalars(select(ProjectClip).where(
        ProjectClip.id.in_({t.clip_id for t in takes.values()})))}  # fmt: skip
    out, at = [], 0.0
    for take in (takes.get(i) for i in (cut.take_ids if cut else [])):
        row = rows.get(take.clip_id) if take else None
        if row is None:
            continue
        piece = row.song_slice or {}
        seconds = (piece["end"] - piece["start"]) if piece else row.seconds
        out.append({"row": row, "take": take, "start": at, "seconds": seconds})
        at += seconds
    return out


def _clip(row: ProjectClip) -> str:
    return f"Clip {row.clip_id.removeprefix('c')}"


def _remade(db: Session, project: Project, spans: list[dict], turns: list[Job]) -> list[dict]:
    """Each clip in the cut whose take the director made again after its watch found
    something: what it found on the take before, and that it remade it, at that moment."""
    asked = {clip: {"text": why} for clip, why in watched(turns).items()}  # the cut's watch
    from app.model_map import of_clip

    out = []
    for s in spans:
        take, row = s["take"], s["row"]
        made = db.get(Job, take.job_id)
        if take.number < 2 or not (made and made.input.get("by_director")):
            continue
        earlier = select(ClipTake.id).where(ClipTake.clip_id == row.id,
                                            ClipTake.number < take.number)  # fmt: skip
        checks = db.scalars(select(ItemCheck).where(ItemCheck.target.in_(("take", "words")),
                                                    ItemCheck.target_id.in_(earlier))
                            .order_by(ItemCheck.id.desc()))  # fmt: skip
        found = next((f for c in checks for f in _found(c)), None) or asked.get(row.clip_id)
        if found is None:  # a remake no watch asked for (a person's note)
            continue
        at = found["at"] if isinstance(found.get("at"), int | float) else 0
        did = ("Remade without them." if found.get("kind") == "text"
               else f"Remade on {_model(take, of_clip(project, row).name)}.")  # fmt: skip
        out.append({"at": round(s["start"] + min(at, s["seconds"]), 1), "clip": row.clip_id,
                    "text": f"{_clip(row)}: {said(found['text']).rstrip('.')}. {did}"})  # fmt: skip
    return out


def _fixed(db: Session, project: Project, spans: list[dict], turns: list[Job]) -> list[dict]:
    """The run's free fixes on clips in the cut (a mute, a spliced word, another take the
    watch picked), as their results said them, at the clip's start, with what the watch of the
    cut found there."""
    from app.watch_cut import state

    found = {f.get("clip_id"): f.get("says", "") for f in state(db, project).get("findings") or []}
    where = {s["row"].clip_id: s for s in spans}
    out = []
    for j in turns:
        tool, clip = (j.output or {}).get("tool"), (j.output or {}).get("clip_id")
        result = j.input.get("result") or ""
        if tool not in FIXES or result.startswith("Refused") or clip not in where:
            continue
        if tool == "pick_take" and clip not in found:
            continue  # its own pick of the best take, not a fix
        head = f"{_clip(where[clip]['row'])}: " + (
            f"{said(found[clip]).rstrip('.')}. " if found.get(clip) else "")  # fmt: skip
        out.append({"at": round(where[clip]["start"], 1), "clip": clip,
                    "text": head + said(result)})  # fmt: skip
    return out


def shown(note: dict | None, owner: bool) -> dict | None:
    """The note as this person reads it, with its cost line in the header's figures at this
    cut (the whole video's, board S3-12): dollars to the owner ("$9.84 spent of up to
    $16.86"), credits only to anyone else ("96 credits used of up to 164 (59% of the
    budget)"). The "up to" is never below what was spent."""
    from app.credits import price
    from app.models.credits import USD_PER_CREDIT

    if not note:
        return None
    used = Decimal(str(note["spent"]))
    up_to = max(Decimal(str(note["up_to"])), used)  # a note from before the guard
    if owner:
        most = math.ceil(up_to * USD_PER_CREDIT * 100) / 100
        cost = f"${dollars(used):.2f} spent of up to ${most:.2f}"
    else:
        pct = round(100 * used / up_to) if up_to else 0
        cost = f"{round(used)} credits used of up to {price(up_to)} ({pct}% of the budget)"
    still = note.get("open", [])
    return {**note, "open": still, "needs": needs(note["needs"], bool(still or note["unsure"])),
            "cost": cost, "up_to": float(up_to),
            "spent_usd": dollars(used) if owner else None}  # fmt: skip


READY = re.compile(
    r"\bready[\s-]+(?:to[\s-]+(?:post|publish|share|upload|go|be[\s-]+(?:posted|shared))|for"
    r"[\s-]+(?:posting|upload(?:ing)?|you(?:[\s-]+to[\s-]+post)?))\b|\bgood[\s-]+to[\s-]+(?:go|post)\b"
    r"|\ball[\s-]+set\b|\b(?:go[\s-]+ahead[\s-]+and|feel[\s-]+free[\s-]+to|you[\s-]+can)[\s-]+post\b"
    r"|\b(?:it|that|everything|the[\s-]+(?:cut|video))(?:(?:'|’)s|[\s-]+is)[\s-]+ready"
    r"(?:[\s-]+(?:to[\s-]+(?:be[\s-]+)?(?:post|publish|share|upload)\w*|for[\s-]+\w+))?\b",
    re.I,
)
FILLER = re.compile(  # words that ask for nothing, once a "nothing" word says so (NONE)
    r"(?i)[\W\s]*(?:(?:nothing|none|no|else|more|action|needed|required|left|to|do|at|this|"
    r"time|is|it|it's|it’s|then|so|and|now|you|you're|you’re|from|me|n/a|ready|be|for|yet|"
    r"here|all|approve|post|posted|posting|share|shared|upload|go)\b[\W\s]*)*"
)
NONE = re.compile(r"(?i)\b(?:nothing|none|no|n/a)\b")
ASKS = re.compile(r"(?i)(?<!to )\b(?:approve|ok|confirm)\b")  # "Nothing else. Approve it."
ACT = re.compile(r"(?i)\b(?:approve|post|share|upload|go|ok|confirm)\w*\b")  # an ask's verbs
MENTIONS = re.compile(r"(?i)\bready\b|\b(?:post|publish|ship|share|upload)\w*\b")
LOOK = "Look at what remains uncertain before you post it."
NOT_YET = "Not ready to post yet."


def needs(said_: str, unsettled: bool) -> str:
    """What I need from you, as the server lets it stand (Reed: a cut that exists isn't ready
    to post). With nothing open or uncertain, the director's words stand. Otherwise it never
    reads as ready, and the director's words are never cut: a note that only says it's ready,
    or that asks for nothing, becomes LOOK_FIRST; anything else is kept word for word, after
    NOT_YET when it mentions being ready or posting, then LOOK."""
    if not unsettled:
        return said_ or NOTHING
    text = re.sub(r"\s+", " ", said_ or "").strip()
    rest = READY.sub(" ", text)
    said_ready = READY.search(text) and not ACT.search(rest)  # "You're all set!": ready only
    if not re.search(r"\w", rest) or (
        FILLER.fullmatch(rest) and ((NONE.search(rest) and not ASKS.search(rest)) or said_ready)
    ):
        return LOOK_FIRST
    text = re.sub(r"[\s;:,—–-]+$", "", text)
    if not re.search(r"[.!?…][\"'”’)\]]*$", text):
        text += "."
    yet = NOT_YET if READY.search(text) or MENTIONS.search(text) else ""
    return " ".join(x for x in (yet, text, LOOK) if x)


def plain(note: dict) -> str:
    """The note as plain lines: the chat's text for a screen that doesn't draw the card."""
    rows = [f"{int(r['at']) // 60}:{int(r['at']) % 60:02d} {r['text']}" for r in note["redid"]]
    return "\n".join(p for p in (note["made"], *rows, note["unsure"], *note.get("open", []),
                                 note["needs"], note["cost"]) if p)  # fmt: skip
