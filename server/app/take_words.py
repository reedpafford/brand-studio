"""The take's words check (docs/next/take-review-checklist.md, part B 1, 2 and 9): after a
take finishes, what it says is heard (the reel import's faster-whisper, free on our server)
and compared with the script's lines for its clip. Advice only, like the item check: it
never blocks and never redoes anything. It runs whenever the item check does
(item_checks.on)."""

import logging
import re
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app import item_checks, plans
from app.models.brands import Brand
from app.models.checks import ItemCheck
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.projects import Project

log = logging.getLogger(__name__)
KIND, STEP, TARGET = "take_listen", "take_words", "words"
SAID = 0.6  # how close a heard line must be to a script line to count as said
# Action wording that a video model tends to say out loud (checklist B 9).
VOICED = re.compile(r"\b(thinks?|thought|wonders?|inner|to (him|her|them)self|repl(y|ies|ied)"
                    r"|answers?|answered)\b", re.I)  # fmt: skip
SHOW = ("Show the feeling instead of saying it: no inner thoughts and no “replies” or "
        "“answers” in the action, only the script's lines.")  # fmt: skip


def _bare(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _close(a: str, b: str) -> float:
    return SequenceMatcher(None, _bare(a), _bare(b)).ratio()


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def _off_by_one(a: str, b: str) -> bool:
    """One letter changed, added or dropped, keeping the first: "Fobo", "FOMA" for fomo."""
    if a == b or abs(len(a) - len(b)) > 1 or a[:1] != b[:1]:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def say(brand: Brand) -> str:
    """How the brand's name is said, from its notes ("Say fomo FOH-moh"), else as written."""
    notes = [brand.tone_notes or "", *(brand.do_list or [])]
    for note in notes:
        if brand.name.lower() in note.lower() and (m := re.search(r"\b[A-Z]+-[A-Za-z-]+\b", note)):
            return m.group(0)
    return brand.name


def _finding(kind: str, at: float | None, text: str, note: str, role: str = "") -> dict:
    return {"kind": kind, "role": role, "at": at, "text": text, "change_note": note}


def compare(lines: list[dict], heard: list[dict], brand: str, said_as: str,
            actions: list[str]) -> list[dict]:  # fmt: skip
    """Findings: script lines not heard, heard lines not in the script (spoken actions when
    the clip's action has inner speech or reply/answer wording) and the brand said wrong."""
    findings, used = [], set()
    for line in lines:
        near = sorted(range(len(heard)), key=lambda i: -_close(line["text"], heard[i]["text"]))
        if near and _close(line["text"], heard[near[0]]["text"]) >= SAID:
            used.add(near[0])
            continue
        who = line.get("who") or ""
        findings.append(_finding("missing", None, f"Not heard: {who + ': ' if who else ''}"
                                 f"“{line['text']}”", f"Make sure {who or 'they'} says, word "
                                 f"for word: “{line['text']}”", who))  # fmt: skip
    voiced = any(VOICED.search(a) for a in actions)
    scripted = {w for line in lines for w in _bare(line["text"]).split()}
    for i, h in enumerate(heard):
        said, at = h["text"].strip(), _clock(h["start"])
        mute = f"It can be muted in the cut ({at}–{_clock(h['end'])})."
        if i not in used and not any(_close(line["text"], said) >= SAID for line in lines):
            if voiced:
                findings.append(
                    _finding(
                        "voiced",
                        h["start"],
                        f"“{said}” at {at} isn't in the script: the action was spoken. {mute}",
                        SHOW,
                    )
                )
            else:
                findings.append(_finding("extra", h["start"], f"“{said}” at {at} isn't in the "
                                         f"script. {mute}", f"Say only the script's lines, "
                                         f"word for word: no “{said}”."))  # fmt: skip
        for word in re.findall(r"[A-Za-z']+", said):
            if word.lower() not in scripted and _off_by_one(word.lower(), brand.lower()):
                findings.append(_finding("name", h["start"], f"“{word}” at {at}: {brand} may "
                                         "be said wrong. Listen first: the transcript can "
                                         f"mishear.", f"Say {brand} as {said_as}, never "
                                         f"“{word}”."))  # fmt: skip
    return findings


def queue(db: Session, job: Job, take_id: int, file_id: int, shots: list[dict],
          prompt: str) -> ItemCheck | None:  # fmt: skip
    """After a take is saved (in the worker): a free listen, when checks are on and its clip
    has spoken lines. Dialogue only: a narrated video's lines are the narrator's and a song
    video's are the song's, heard over the take, not said in it."""
    project = db.get(Project, job.project_id) if job.project_id else None
    lines = [{"who": s.get("speaker") or "", "text": s["line"]} for s in shots if s.get("line")]
    if not project or not item_checks.on() or not lines or plans.fmt(db, project) != "dialogue":
        return None
    brand = db.get(Brand, project.brand_id)
    row = ItemCheck(project_id=project.id, target=TARGET, target_id=take_id, status="checking")
    db.add(row)
    db.flush()
    data = {"step": STEP, "item_check_id": row.id, "project_id": project.id,
            "video_key": db.get(StoredFile, file_id).key, "lines": lines, "prompt": prompt or "",
            "actions": [s.get("action") or "" for s in shots],
            "brand": brand.name, "said_as": say(brand)}  # fmt: skip
    listen = Job(workspace_id=project.workspace_id, created_by_id=job.created_by_id, kind=KIND,
                 provider="local", input=data, project_id=project.id, brand_id=project.brand_id,
                 credits=0, status="queued")  # fmt: skip
    db.add(listen)
    db.flush()
    row.job_id = listen.id
    return row


def queue_safely(db: Session, *args) -> None:
    """A check never stops a take from being saved."""
    try:
        with db.begin_nested():
            queue(db, *args)
    except Exception:
        log.exception("couldn't queue the words check for take %s", args[1])


def save(db: Session, job: Job) -> None:
    row = db.get(ItemCheck, job.input.get("item_check_id") or 0)
    if not row:
        return
    i = job.input
    row.findings = compare(i["lines"], (job.output or {}).get("heard", []), i["brand"],
                           i["said_as"], i["actions"])  # fmt: skip
    row.status = "done"
    from app.take_approval import after_check

    db.flush()
    after_check(db, row.target_id)  # a clean picked take approves itself (rule 21)
