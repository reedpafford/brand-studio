"""The take's words check (docs/next/take-review-checklist.md, part B 1, 2 and 9): after a
take finishes, what it says is heard (the reel import's faster-whisper, free on our server)
and compared with the script's lines for its clip. Advice only, like the item check: it
never blocks and never redoes anything. It runs whenever the item check does
(item_checks.on). In a song or narrated video nobody speaks on screen, so any voice heard is
the finding (Song-Producer), muted at once where the take's sound is kept (narrated)."""

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
# Non-speech sounds: whisper's own tags ("(gasps)", "[breathing]", "*sigh*"), and lines that
# are only a breath ("Haah!", "Huh."). Gasps are allowed when they serve the moment (Reed,
# 1 Nov: "We CAN have gasps, I just want the director to THINK"): only one the script or the
# clip's action doesn't ask for ("she sighs"), or a second one in a clip, is Advice.
SOUNDS = ("gasp", "sigh", "breath", "pant", "groan", "moan", "scream", "grunt", "sob", "laugh",
          "cough", "huff", "wheez")  # fmt: skip
TAG = re.compile(r"[(\[*]\s*([a-z ]+?)\s*[)\]*]", re.I)
BREATH = re.compile(r"(a+h+|h+a+h*|hu+h|o+h+|u+h+|hm+|phew|whew)[.!?…\s]*", re.I)
UNASKED = "A gasp here isn't asked for by the script; keep it only if it serves the moment."
REPEAT = "One gasp or breath in this clip at most, where it serves the moment."
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


def _finding(kind: str, at: float | None, text: str, note: str, role: str = "",
             span: list[float] | None = None) -> dict:  # fmt: skip
    """`span`: the stretch the card can offer to mute (take_mute), when muting fixes it."""
    return {"kind": kind, "role": role, "at": at, "text": text, "change_note": note,
            **({"span": span} if span else {})}  # fmt: skip


def _sound(tag: str) -> bool:
    return any(w in tag.lower() for w in SOUNDS)


def _sounds(heard: list[dict], asked: str, lines: list[str]) -> tuple[list[dict], list[dict]]:
    """The non-speech sounds heard, as findings, and the heard lines with them taken out. A
    sound the script or the action asks for ("(gasps)", "she sighs") is left alone, unless
    it's a second one in the clip. A breath-like line the script has ("MIA: Oh.") is a line."""
    found, spoken, count = [], [], 0
    for h in heard:
        at, span = _clock(h["start"]), f"{_clock(h['start'])}–{_clock(h['end'])}"
        tags = [f"({t})" for t in TAG.findall(h["text"]) if _sound(t)]
        rest = TAG.sub("", h["text"]).strip()  # no tag is a line: "(music)", "[applause]"
        scripted = any(_close(rest, line) >= SAID for line in lines)
        if BREATH.fullmatch(rest) and not scripted:  # only a breath: "Haah!"
            tags, rest = [*tags, rest.strip(" .!?…")], ""
        for t in tags:
            count += 1
            wanted = any(w in t.lower() and w in asked for w in SOUNDS) or (
                BREATH.fullmatch(t) and any(w in asked for w in ("gasp", "breath", "sigh"))
            )
            if wanted and count == 1:
                continue
            alone = f" It can be muted in the cut ({span})." if not rest else ""  # else: a redo
            why, note = (("another gasp or breath in this clip", REPEAT) if wanted or count > 1
                         else ("a gasp or breath the script doesn't ask for", UNASKED))  # fmt: skip
            found.append(_finding("sound", h["start"], f"“{t}” at {at}: {why}.{alone}", note))
        if rest:
            spoken.append({**h, "text": rest})
    return found, spoken


def compare(lines: list[dict], heard: list[dict], brand: str, said_as: str,
            actions: list[str]) -> list[dict]:  # fmt: skip
    """Findings: script lines not heard, heard lines not in the script (spoken actions when
    the clip's action has inner speech or reply/answer wording), the brand said wrong, and
    gasps or heavy breaths nobody asked for."""
    asked = " ".join([*actions, *(line["text"] for line in lines)]).lower()
    findings, heard = _sounds(heard, asked, [line["text"] for line in lines])
    sounds, findings, used = findings, [], set()
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
                        span=[h["start"], h["end"]],
                    )
                )
            else:
                findings.append(_finding("extra", h["start"], f"“{said}” at {at} isn't in the "
                                         f"script. {mute}", f"Say only the script's lines, "
                                         f"word for word: no “{said}”.",
                                         span=[h["start"], h["end"]]))  # fmt: skip
        for word in re.findall(r"[A-Za-z']+", said):
            if word.lower() not in scripted and _off_by_one(word.lower(), brand.lower()):
                findings.append(_finding("name", h["start"], f"“{word}” at {at}: {brand} may "
                                         "be said wrong. Listen first: the transcript can "
                                         f"mishear.", f"Say {brand} as {said_as}, never "
                                         f"“{word}”."))  # fmt: skip
    return findings + sounds


VOICE = ("“{said}” at {at} is said in the take, but nobody speaks or sings on screen in a "
         "{kind} video.")  # fmt: skip
NO_VOICE = "Nobody speaks or sings on screen: picture only, the {kind} carries every word."


def voices(heard: list[dict], kind: str = "song or narrated") -> list[dict]:
    """A song or narrated video's take (Song-Producer): every line heard in it is a fault,
    offered for a mute (a narrated video keeps the take's sound under the narrator)."""
    _, spoken = _sounds(heard, "", [])
    return [_finding("voiced", h["start"], VOICE.format(said=h["text"].strip(),
                                                         at=_clock(h["start"]), kind=kind),
                     NO_VOICE.format(kind="narrator" if kind == "narrated" else "song"),
                     span=[h["start"], h["end"]]) for h in spoken if h["text"].strip()]  # fmt: skip


def _mute_voices(db: Session, row: ItemCheck) -> None:
    """A narrated video plays its takes' own sound under the narrator: voices in it are
    muted at once (free, undoable on the clip); a song video drops the take's sound anyway."""
    from app import take_mute
    from app.models.clips import ClipTake, ProjectClip

    project = db.get(Project, row.project_id)
    take = db.get(ClipTake, row.target_id)
    if not take or not row.findings or plans.fmt(db, project) != "narrated":
        return
    longest = float(db.get(ProjectClip, take.clip_id).seconds)
    for f in row.findings:
        if f.get("span") and list(f["span"]) not in take_mute.spans(take):
            try:
                take_mute.add(take, f["span"][0], f["span"][1], longest)
            except ValueError:
                continue


def queue(db: Session, job: Job, take_id: int, file_id: int, shots: list[dict],
          prompt: str) -> ItemCheck | None:  # fmt: skip
    """After a take is saved (in the worker): a free listen, when checks are on and its clip
    has spoken lines. Dialogue only: a narrated video's lines are the narrator's and a song
    video's are the song's, heard over the take, not said in it."""
    project = db.get(Project, job.project_id) if job.project_id else None
    if not project or not item_checks.on():
        return None
    silent = plans.fmt(db, project) != "dialogue"  # a song's or narrator's: nobody speaks
    lines = [] if silent else [{"who": s.get("speaker") or "", "text": s["line"]}
                               for s in shots if s.get("line")]  # fmt: skip
    if not lines and not silent:
        return None
    brand = db.get(Brand, project.brand_id)
    row = ItemCheck(project_id=project.id, target=TARGET, target_id=take_id, status="checking")
    db.add(row)
    db.flush()
    data = {"step": STEP, "item_check_id": row.id, "project_id": project.id,
            "video_key": db.get(StoredFile, file_id).key, "lines": lines, "prompt": prompt or "",
            "actions": [s.get("action") or "" for s in shots],
            "brand": brand.name, "said_as": say(brand), "silent": silent}  # fmt: skip
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
    i, heard = job.input, (job.output or {}).get("heard", [])
    if i.get("silent"):  # a song or narrated video's take: any voice is a fault
        row.findings = voices(heard, plans.fmt(db, db.get(Project, row.project_id)))
        _mute_voices(db, row)
    else:
        row.findings = compare(i["lines"], heard, i["brand"], i["said_as"], i["actions"])
    row.status = "done"
    from app.take_approval import after_check

    db.flush()
    after_check(db, row.target_id)  # a clean picked take approves itself (rule 21)
