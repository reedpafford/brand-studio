"""An editor asks to change a locked line (S3-14): a published script's words are set, so a
note that asks to replace or reword the script's own words is answered at once, free and with
no model call, with what can change instead, each priced as its press charges ("up to"; an
editor reads credits). Only what this video can really make is offered; with nothing, the note
waits for the director as any note does. A note that asks for more than the word change keeps
the rest for the director (it stays unread for the next Make it).

The card is an `Ask` of kind "instead": never a question a run waits on, never in Needs you
(its state is "offered"). A press makes its choice at once (`DOES`). "Say it softer" is a new
take of the clip that says the words, through Make a take's own price and holds; once its watch
comes back clean that clip is approved and the cut is made again (free, rule 35: never a cut
from a take nobody watched). Each choice keeps what happened to it on the card
(`answer.chosen`); the other choices stay pressable."""

import logging
import re
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

log = logging.getLogger(__name__)
KIND = "instead"
OFFERED = "offered"  # its state: answered by the server; never a question that waits
FOR = "instead_for"  # in a take job's input: [the card, the choice] whose press made it
SET = "The script’s words are set for this script, so I can’t change “{}”. Here’s what I can change instead:"  # noqa: E501
SET_ONLY = "The script’s words are set for this script, so I can’t change “{}”."  # nothing to
# offer instead here: the note is answered all the same, and no run starts for it
SOFTER_NOTE = "Say it more softly and warmly, with less edge. Every word stays as written."
RUNNING = "The director is working on this video. Tell it in the chat instead."
QUOTE = re.compile(r"[“\"]([^”\"]{2,80})[”\"]|(?<![\w’'])[‘']([^’']{2,80})[’'](?![\w])")
# what a word change says around the quoted words ("Q" stands for them; "R" for a replacement)
ASKS = (
    r"\b(?:change|swap|replace|switch)\s+(?:the\s+)?(?:(?:word|words|line|phrase|bit)\s+)?Q"
    r"\s*(?:to|with|for|into|by)\s+R",  # "change "beer gut" to "belly"": a quoted replacement
    r"\b(?:reword|rewrite|rephrase)\s+(?:the\s+)?(?:(?:word|words|line|phrase|bit)\s+)?Q",
    r"\b(?:say|use|write|put)\s+R\s+instead\s+of\s+Q",
    r"R\s+instead\s+of\s+Q",
    r"\binstead\s+of\s+Q\s*,?\s*(?:say|use|write|put)\s+R",
)
UNSAID = re.compile(  # with no quotes (video 245: "Ray should say a coin flip, not a slot machine")
    r"(?:\b(?P<who>[\w.'’-]+)\s+(?:should|could|can|would|needs?\s+to|has\s+to|must)\s+)?"
    r"\bsays?\s+"
    r"(?P<r>[^,.;!?“”\"]+?)\s*,?\s+(?:not|instead\s+of|rather\s+than)\s+(?P<q>[^,.;!?“”\"]+)",
    re.I,
)
ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.I)
HOW = re.compile(  # what follows "say" is how it's said, not other words (QA on #1429)
    r"^(?:it|that|this|them|him|her|these|those|like|with|more|less|so|too|much|way|"
    r"a\s+(?:bit|little|lot)|\w+ly|\w+er)\b",
    re.I,
)
POLITE = re.compile(
    r"^(?:(?:can|could|would|will)\s+(?:we|you|i|it\s+be)\b|please\b|maybe\b)\s*", re.I
)
TONE = (
    "harsh|rude|mean|cringe|cringey|cringy|off|wrong|much|crude|blunt|aggressive|offensive|"
    "crass|cheesy|insulting|negative|judgy|judgmental|preachy|weird|"
    "awkward|snarky|condescending|gross|edgy|unkind|pushy|salesy|forced"
)
REASON = re.compile(  # a bare verdict on the words' tone: "It feels a bit harsh." (never the
    # picture or the sound: "It's too dark." stays for the director)
    r"^(?:it|that|this)(?:['’]s|\s+(?:is|feels|sounds|reads|seems|comes\s+across))"
    rf"(?:\s+(?:a\s+bit|a\s+little|too|so|quite|kind\s+of|really|very))?\s+(?:{TONE})$",
    re.I,
)


def _plain(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("‘", "'").lower().split())


def _in(words: str, text: str) -> bool:
    """`words` said in `text` as whole words ("pin" isn't in "pint")."""
    return bool(re.search(rf"(?<!\w){re.escape(_plain(words))}(?!\w)", _plain(text)))


def asked(text: str, script: str) -> tuple[str, bool] | None:
    """The script's words a note asks to replace or reword, and whether that's all the note
    asks; None when it doesn't ask that."""
    found = asked_for(text, script)
    return (found[0], found[2]) if found else None


def asked_for(text: str, script: str) -> tuple[str, str | None, bool] | None:
    """As `asked`, with the words it asks for instead (None: "reword it", no new words)."""
    quotes = [(m.group(0), (m.group(1) or m.group(2)).strip()) for m in QUOTE.finditer(text)]
    for raw, words in quotes:
        if not words or not _in(words, script):
            continue
        new = [re.escape(r) for r, w in quotes if w != words and not _in(w, script)]
        repl = f"(?:{'|'.join(new)})" if new else r"(?!x)x"
        fill = {"Q": re.escape(raw), "R": f"(?P<r>{repl})"}  # in one pass: never inside the
        for pattern in ASKS:  # quoted words themselves (video 261: "Resilia" has an R)
            found = re.search(re.sub("[QR]", lambda m, f=fill: f[m[0]], pattern), text, re.I)
            if found:
                new = (found.groupdict().get("r") or "").strip("“”\"'‘’ ") or None
                return words, new, _only(text[: found.start()] + " " + text[found.end() :])
    for found in UNSAID.finditer(text):  # "say R, not Q": Q the speaker's words, R new ones
        new = found["r"].strip()
        if HOW.match(new):  # "say it slower, not fast": a delivery note, the director's
            continue
        old = re.sub(r"\s+(?:please|instead|thanks)$", "", found["q"].strip(), flags=re.I)
        said, named = _lines(script, found["who"])
        least = 1 if named else 2  # one word only in a named speaker's own line (QA on #1429)
        words = next((w for w in (old, ARTICLE.sub("", old))
                      if len(w.split()) >= least and len(w) > 2 and _in(w, said)),
                     None)  # fmt: skip
        if words and not _in(new, script):
            return words, new, _only(text[: found.start()] + " " + text[found.end() :])
    return None


def _lines(script: str, who: str | None) -> tuple[str, bool]:
    """The words the script gives `who` to say ("Ray": UNCLE RAY's lines), and True; or every
    spoken line, and False, when no one is named or no speaker has that name."""
    spoken = [ln.split(":", 1) for ln in script.splitlines() if ":" in ln]
    mine = [said for name, said in spoken if who and re.search(rf"(?<!\w){re.escape(who)}(?!\w)",
                                                               name, re.I)]  # fmt: skip
    return "\n".join(mine or [said for _, said in spoken]), bool(mine)


SCAFFOLD = re.compile(  # "Nate should say … , not": what's left of an unquoted word change
    r"(?:\b[\w.'’-]+\s+(?:should|could|can|would|needs?\s+to|has\s+to|must)\s+)?\bsays?\s+"
    r"[^,.;!?]*?\s*,?\s+(?:not|instead\s+of|rather\s+than)\b",
    re.I,
)


def only_words(text: str, words: str) -> bool:
    """A note that asks only to change these words, and nothing more (the director's card ends
    a run only then): what's left once the word change is taken out is empty or a reason."""
    if (found := asked(text, words)) is not None and found[0] == words:
        return found[1]
    rest = re.sub(rf"[“\"‘']?{re.escape(words)}[”\"’']?", " ", text, flags=re.I)
    return _only(SCAFFOLD.sub(" ", rest))


def _only(rest: str) -> bool:
    """What's left of a note once its word change is taken out says nothing more: empty, or a
    short reason about those words. Anything else stays for the director (unread)."""
    for part in re.split(r"[.!?;\n]+", rest):
        part = POLITE.sub("", part.strip(" ,—-")).strip(" ,—-")
        if part and not REASON.match(part):
            return False
    return True


def offer(db: Session, user: User, project: Project, text: str) -> tuple[Ask, bool] | None:
    """The reply to a note asking to change the script's words, and whether the note asked only
    that; None (not such a note, not a published script's video, or nothing can be made)."""
    from app import plans

    version = plans.script(db, project)
    if not project.script_draft_id or version is None:
        return None
    found = asked_for(text, version.text)
    if found is None:
        return None
    words, new, only = found
    choices = _choices(db, user, project, words, new)
    if not choices and not only:
        return None  # nothing to offer, and it asks more: the director reads all of it
    return card(db, project, words, choices, owner=user.is_owner), only


def _choices(db: Session, user: User, project: Project, words: str,
             new: str | None = None) -> list[dict]:  # fmt: skip
    """What can change instead, and for the owner first "Change the line" (Reed, 7 Nov)."""
    from app import line_change

    shot = _said_in(db, project, words)
    return [c for c in (line_change.choice(db, user, project, words, new),
                        _softer(db, project, shot), _safely(_cut_away, db, user, project, words),
                        _safely(_pause, db, user, project, words)) if c]  # fmt: skip


POSTED = ("Answered at once: the script's words are set, so I offered what can change "
          "instead.")  # fmt: skip
NOT_SCRIPT = ("Refused: “{}” isn't in the published script. Give the script's words exactly as "
              "it has them.")  # fmt: skip


def for_director(db: Session, user: User, project: Project, words: str | None, why: str,
                 run_id: str | None, new: str | None = None) -> str:  # fmt: skip
    """The director's `locked_line` (free): S3-14's card for a person's note that asks to change
    the published script's words and that no card answered as it came (QA on #1429: "Ray should
    say sure, not okay" started a run that re-delivered with the refusal buried). The notes its
    `why` names are answered by the card."""
    from app import plans
    from app.director import NOTE

    version = plans.script(db, project)
    words = (words or "").strip().strip("“”\"'‘’ ")
    if not project.script_draft_id or version is None or not words or not _in(
            words, version.text):  # fmt: skip
        return NOT_SCRIPT.format(words)
    ask = card(db, project, words, _choices(db, user, project, words, new),
               owner=user.is_owner)  # fmt: skip
    mine = [n for n, m in enumerate(project.director_chat or []) if m.get("run") == run_id]
    chat = list(project.director_chat or [])
    for n in {int(x) for x in NOTE.findall(why)}:
        if 1 <= n <= len(mine):
            chat[mine[n - 1]] = {**chat[mine[n - 1]], "offer": ask.id}  # answered by the card
    project.director_chat = chat
    db.flush()
    return POSTED


OWNS = "You can change “{}” in a new version of the script, or change how it plays instead:"


def card(db: Session, project: Project, words: str, choices: list[dict],
         owner: bool = False) -> Ask:  # fmt: skip
    """S3-14's card: the words are set, and what can change instead (or nothing to offer); the
    owner's offers "Change the line" first (rule 31's owner exception, Reed 7 Nov)."""
    from app import line_change

    mine = owner and any(c.get("do") == line_change.DO for c in choices)
    said = OWNS if mine else SET if choices else SET_ONLY
    ask = Ask(workspace_id=project.workspace_id, project_id=project.id, kind=KIND,
              subject=words[:120], question=said.format(words),
              state=OFFERED,
              choices=[{"key": chr(65 + n), **c} for n, c in enumerate(choices)])  # fmt: skip
    db.add(ask)
    db.flush()
    return ask


def _said_in(db: Session, project: Project, words: str) -> dict | None:
    """The newest shots' shot that says these words: {clip, speaker}, or None."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    if bd is None:
        return None
    clip_of = {s: c["id"] for c in bd.data.get("clips", []) for s in c["shot_ids"]}
    for scene in bd.data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("line") and _in(words, shot["line"]) and shot["id"] in clip_of:
                return {"clip": clip_of[shot["id"]], "speaker": shot.get("speaker") or ""}
    return None


def _softer(db: Session, project: Project, shot: dict | None) -> dict | None:
    """ "Say it softer": a new take of the clip that says it, its voice with it. Only where the
    clip's take carries the voice: a dialogue video's clip with a take in the cut (a narration,
    a song or a presenter is said elsewhere, and a UGC talker's clips come from its one take)."""
    if shot is None or _voiced(db, project, shot["clip"]):
        return None
    row = _row(db, project, shot["clip"])
    if row is None or row.picked_take_id is None:
        return None
    who = _name(shot["speaker"])
    said = f"{who} says it more softly" if who else "It's said more softly"
    n = shot["clip"].removeprefix("c")
    return {"title": "Say it softer", "why": f"{said}. Redo the voice line and clip {n}",
            "do": "softer", "clip": shot["clip"]}  # fmt: skip


# --- In the cut (#1299's edits, free): where the words are said, and what can change there ----


class _DryRun(Exception):
    """Raised inside a savepoint to take back an edit tried only to see that it goes through."""


def _goes(db: Session, user: User, project: Project, kind: str, asked: dict) -> bool:
    """Whether this edit to the cut goes through now (every check the editor's own has: no
    spoken word cut, a piece no shorter than its least), tried and taken back."""
    from app import cut, cut_edits

    try:
        with db.begin_nested():
            cut_edits.add(db, user, project, kind, asked)
            raise _DryRun
    except _DryRun:
        return True
    except cut.Refused:
        return False
    except Exception:  # one bad cut never breaks the cards: it just can't be offered now
        log.exception("project %s: trying a %s edit for a locked line failed", project.id, kind)
        return False


def _safely(offer_it, db: Session, user: User, project: Project, words: str) -> dict | None:
    """A cut choice to offer, or None: a cut that can't be read never stops the reply."""
    try:
        return offer_it(db, user, project, words)
    except Exception:
        log.exception("project %s: offering a locked line's cut choice failed", project.id)
        return None


def _spoken(tl: dict, words: str) -> tuple[float, float, int] | None:
    """Where the cut says these words: (start, end, the index of their last word), or None."""
    want = re.findall(r"[a-z0-9']+", _plain(words))
    heard = [re.sub(r"[^a-z0-9']", "", _plain(w["word"])) for w in tl["words"]]
    for i in range(len(heard) - len(want) + 1):
        if want and heard[i : i + len(want)] == want:
            j = i + len(want) - 1
            return tl["words"][i]["start"], tl["words"][j]["end"], j
    return None


def _cut_away(db: Session, user: User, project: Project, words: str) -> dict | None:
    """ "Cut away while it's said": the presenter hidden over the line that says the words, so
    the B-roll under it shows (free). Only in a video with a presenter laid over the B-roll
    (a UGC talker is in its own clips: they can't be swapped for B-roll)."""
    from app import cut

    span = _away_span(db, project, words)
    if span is None or not _goes(
        db, user, project, "presenter", {"start": span[0], "end": span[1], "hidden": True}
    ):
        return None
    tl, _ = cut.timeline(db, project)
    name = tl["presenter"]["name"]
    name = name[0].lower() + name[1:] if name.startswith("The ") else name  # "the presenter"
    return {
        "title": "Cut away while it’s said",
        "why": f"Show the B-roll instead of {name}’s face on that line",
        "do": "cut_away",
    }


def _away_span(db: Session, project: Project, words: str) -> tuple[float, float] | None:
    """The line that says the words, in cut seconds (at least a piece's least)."""
    from app import cut

    if cut.newest(db, project) is None:
        return None
    tl, _ = cut.timeline(db, project)
    said = _spoken(tl, words) if tl["presenter"] else None
    if said is None:
        return None
    a, b, _ = said
    line = next(((s, e) for s, e in tl.get("lines") or [] if s <= a < e), None)
    a, b = line if line else (a, b)
    return round(a, 2), round(max(b, a + cut.MIN), 2)


def _pause(db: Session, user: User, project: Project, words: str) -> dict | None:
    """ "Shorter pause after it": in a dialogue video, the clip that says these words (its
    line) trimmed to just after its last spoken word ("Tighten 0.4 s", free). A narration's or
    a song's own pauses are in its audio, so they can't be tightened here."""
    edit = _pause_edit(db, project, words)
    if edit is None or not _goes(db, user, project, "trim", edit[0]):
        return None
    return {"title": "Shorter pause after it", "why": _pause_why(edit), "do": "pause"}


def _pause_why(edit: tuple[dict, float, bool]) -> str:
    """ "Tighten 0.4 s"; after the clip's last spoken word when the words are mid-line."""
    return f"Tighten {edit[1]:g} s" + (" after the clip’s last spoken word" if edit[2] else "")


PAUSE = 0.2  # seconds: a pause shorter than this after the words is left as it is


def _pause_edit(db: Session, project: Project,
                words: str) -> tuple[dict, float, bool] | None:  # fmt: skip
    """The trim that tightens the pause after the words' line, by how much, and whether the
    words are mid-line (it trims after the clip's last spoken word); None if none."""
    from app import cut

    if cut.newest(db, project) is None:
        return None
    tl, _ = cut.timeline(db, project)
    said = _spoken(tl, words) if tl["mode"] == "takes" else None
    if said is None:
        return None
    _, said_end, _ = said
    piece = next((p for p in tl["pieces"] if p["start"] <= said_end <= p["end"]), None)
    if piece is None:
        return None
    end = max(w["end"] for w in tl["words"] if piece["start"] <= w["start"] < piece["end"])
    mid = end > said_end + 0.01
    gap = round(piece["end"] - end - cut.TAIL, 1)  # after its line: its last spoken word
    if gap < PAUSE:
        return None
    return {"piece": piece["id"], "end": round(end + cut.TAIL, 2)}, gap, mid


def _voiced(db: Session, project: Project, clip: str) -> bool:
    """The line is said outside the clip's take: a song or narrated video (a presenter's
    narration too), or a UGC talker's clip."""
    from app import director_song, host, talker

    return bool(director_song.kind(db, project) or host.on(db, project)
                or clip in talker.clips(db, project))  # fmt: skip


def _name(speaker: str) -> str:
    """ "DR. PICKLE" as people write it: "Dr. Pickle"."""
    return " ".join(w.capitalize() for w in speaker.split()) if speaker.isupper() else speaker


def _row(db: Session, project: Project, clip: str) -> ProjectClip | None:
    return db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                               ProjectClip.clip_id == clip))  # fmt: skip


# --- A choice on the card: whether it can be made, its price, its press, what happened -------


def cannot(db: Session, project: Project, choice: dict, words: str = "",
           user: User | None = None) -> str:  # fmt: skip
    """Why this choice can't be made now ("" when it can), checked when shown and pressed."""
    from app import director

    if director.active(db, project):
        return RUNNING
    if choice.get("do") == "change_line":
        from app import line_change

        return line_change.cannot(db, project, choice, words, user)
    if choice.get("do") == "softer":
        row = _row(db, project, choice.get("clip") or "")
        n = (choice.get("clip") or "").removeprefix("c")
        if row is None:
            return f"Clip {n} isn't in this video any more."
        if row.picked_take_id is None or _voiced(db, project, row.clip_id):
            return f"Clip {n} has no take of its own in the cut now."
        return ""
    if choice.get("do") in ("cut_away", "pause"):
        return now(db, project, choice, words)[1]
    return "This can't be made here."


def director_going(db: Session, project: Project) -> bool:
    from app import director

    return director.active(db, project) is not None


UNSURE = "The cut can't be read for this right now. Change it in the Cut tab instead."


def now(db: Session, project: Project, choice: dict, words: str) -> tuple[str, str]:
    """A cut choice as it stands now, worked out again whenever it's shown or pressed: its
    detail line ("Tighten 0.4 s") and why it can't be made ("" when it can; tried and taken
    back, as the cut editor would take it). A cut that can't be read never breaks the card."""
    try:
        return _now(db, project, choice, words)
    except Exception:
        log.exception("project %s: working out a locked line's %s failed", project.id,
                      choice.get("do"))  # fmt: skip
        return choice.get("why", ""), UNSURE


def _now(db: Session, project: Project, choice: dict, words: str) -> tuple[str, str]:
    from app import cut

    why = choice.get("why", "")
    if job := cut.making(db, project):
        return why, f"Cut {job.input.get('number')} is being made; try again when it's ready."
    if cut.newest(db, project) is None:
        return why, "There's no cut yet."
    user = db.get(User, project.created_by_id)
    if choice["do"] == "pause":
        edit = _pause_edit(db, project, words)
        if edit is None:
            return why, "The pause after it is already short."
        why, kind, asked = _pause_why(edit), "trim", edit[0]
    else:
        span = _away_span(db, project, words)
        if span is None:
            return why, "The cut doesn't show the presenter while those words are said."
        kind, asked = "presenter", {"start": span[0], "end": span[1], "hidden": True}
    if not _goes(db, user, project, kind, asked):
        return why, "The cut can't take that edit now. Change it in the Cut tab instead."
    return why, ""


def price(db: Session, project: Project, choice: dict) -> Decimal | None:
    """What a choice's press can charge, as that press quotes it (0: free; None: it can't be
    made now, so it has no price)."""
    from app.clip_takes import take_credits

    if choice.get("do") == "softer":
        row = _row(db, project, choice.get("clip") or "")
        return take_credits(db, project, row) if row is not None else None
    if choice.get("do") in ("cut_away", "pause"):
        return Decimal(0)  # an edit and the cut made again: free
    if choice.get("do") == "change_line":
        from app import line_change

        return line_change.price(db, project, choice)
    return None


def made(db: Session, ask: Ask, key: str) -> tuple[str, str, int | None]:
    """A pressed choice's state, its words and the take its free "Use take N and make the cut"
    would use (rule 22: a one-click fix on the card), or None. ("", …) not pressed (or its take
    failed, so it can be pressed again: its words say so); held, making, watching, done or
    kept. A take whose watch remake failed or was declined has no live job left: it says so
    and offers its press, so a card never waits forever."""
    mine = ((ask.answer or {}).get("chosen") or {}).get(key)
    if not mine:
        return "", "", None
    if mine.get("run"):  # "Change the line": its run's own state
        from app import line_change

        return (*line_change.made(db, mine), None)
    if mine.get("edit"):
        from app.models.clips import CutEdit

        edit = db.get(CutEdit, mine["edit"])
        if edit is None or edit.undone_at is not None:  # taken back in the Cut tab
            return "", "Undone in the Cut tab.", None
    if "outcome" in mine:
        use = mine.get("use")
        if use and _gone(db, ask, use):  # its take or clip went since (a new plan): no press
            return "kept", GONE, None
        return ("done" if mine.get("cut") else "kept"), mine["outcome"], use
    job = db.get(Job, mine.get("job") or 0)
    if job is None or job.status in (JobStatus.failed, JobStatus.cancelled):
        return "", "It wasn’t made, and nothing was charged. You can press it again.", None
    if job.status == JobStatus.needs_owner_approval:
        return "held", "Waiting for the owner’s OK.", None
    if job.status != JobStatus.succeeded:
        return "making", "Being made. Its watch looks at it before the cut is made again.", None
    take, live = _chain(db, job)
    if live is not None and live.status == JobStatus.needs_owner_approval:
        return "held", "Made. Its watch asked to make it again: waiting for the owner’s OK.", None
    if live is not None:
        return "watching", "Made. Being watched before the cut is made again.", None
    if take is None:
        return "kept", "It wasn’t made. You can press it again.", None
    n = db.get(ProjectClip, take.clip_id).clip_id.removeprefix("c")
    watch = take.watch or {}
    if watch.get("action") in ("redo", "held", "flagged"):  # its watch found a fault: no press
        found = (watch.get("found") or watch.get("did") or "something to fix").rstrip(".")
        return "kept", (f"Made, but its watch found: {found}. Its remake wasn’t made, so the "
                        f"cut stays as it was; look at clip {n} in Clips."), None  # fmt: skip
    return "kept", (f"Made, but its watch didn’t finish, so the cut stays as it was. Use take "
                    f"{take.number} and make the cut, or look at it in Clips first."
                    ), take.id  # fmt: skip


GONE = "That take isn’t in this video any more."


def _gone(db: Session, ask: Ask, take_id: int) -> bool:
    """Whether a take a card would use went since: deleted, or its clip left this video."""
    take = db.get(ClipTake, take_id)
    row = db.get(ProjectClip, take.clip_id) if take else None
    return row is None or row.project_id != ask.project_id


def _chain(db: Session, job: Job) -> tuple[ClipTake | None, Job | None]:
    """A choice's take and the remakes its watch made of it: (the newest take there is, a job
    on it still going: a remake being made or held, or its watch), following each remake."""
    from app.models.jobs import WAITING
    from app.take_watch import REDO

    take = db.scalar(select(ClipTake).where(ClipTake.job_id == job.id))
    while take is not None:
        remake = db.scalar(select(Job).where(Job.kind == "video",
                                             Job.input[REDO].as_integer() == take.id)
                           .order_by(Job.id.desc()).limit(1))  # fmt: skip
        if remake is None:
            break
        if remake.status in WAITING:
            return take, remake
        newer = db.scalar(select(ClipTake).where(ClipTake.job_id == remake.id))
        if newer is None:  # the remake failed or was declined: this take is the newest
            break
        take = newer
    if take is None:
        return None, None
    watching = db.scalars(select(Job).where(Job.project_id == job.project_id,
                                            Job.status.in_(WAITING))).all()  # fmt: skip
    for j in watching:
        if (j.input.get("take_id") or (j.input.get("watch") or {}).get("take_id")) == take.id:
            return take, j
    return take, None


def choose(db: Session, user: User, ask: Ask, key: str, storage, option=None) -> None:
    """A press on one of the card's choices: made at once, through its own route; or its free
    "Use take N and make the cut" (`option` "use") once its take is made."""
    found = next((c for c in ask.choices if c["key"] == key), None)
    if found is None:
        raise HTTPException(422, "Pick one of the choices on the card.")
    if option not in (None, "use"):
        raise HTTPException(422, "That isn't a way to answer this card.")
    project = db.get(Project, ask.project_id)
    state, said, use = made(db, ask, key)
    if option == "use":
        if use is None:
            raise HTTPException(409, GONE if said == GONE else "There's no take to use here.")
        from app import director

        if director.active(db, project):
            raise HTTPException(409, RUNNING)
        said, cut = _cut(db, project, db.get(ClipTake, use), storage, user, chosen=True)
        return _outcome(db, ask, key, said, cut=cut)
    if state in ("held", "making", "watching"):
        raise HTTPException(409, "That's already being made.")
    if state == "done":
        raise HTTPException(409, "That's made already.")
    if why := cannot(db, project, found, ask.subject, user):
        raise HTTPException(403 if why == _owner_only() else 409, why)
    if state:  # made already (done, or kept with what happened): say that, not "being made"
        raise HTTPException(409, GONE if said == GONE else "That's made already.")
    done = DOES[found["do"]](db, user, project, ask, found, storage)
    from app.db import utcnow

    chosen = {**((ask.answer or {}).get("chosen") or {}), key: done}
    ask.answer = {"how": KIND, "choice": key, "name": found["title"], "chosen": chosen}
    ask.answered_by_id, ask.answered_at = user.id, utcnow()
    db.commit()


def _say_softer(db: Session, user: User, project: Project, ask: Ask, choice: dict,
                storage) -> dict:  # fmt: skip
    """A new take of its clip through Make a take's own route (its price, its holds)."""
    from app.routes import project_clips

    row = _row(db, project, choice["clip"])
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    out = project_clips.generate(project_id=project.id, clip_id=row.id, request=request,
                                 body=project_clips.TakeIn(note=SOFTER_NOTE), user=user,
                                 db=db)  # fmt: skip
    job = db.get(Job, out.id)
    job.input = {**job.input, FOR: [ask.id, choice["key"]]}
    return {"job": job.id}


def _edit_the_cut(db: Session, user: User, project: Project, ask: Ask, choice: dict,
                  storage) -> dict:  # fmt: skip
    """Cut away, or a shorter pause: the edit (free, the person's, with Undo in the cut editor),
    worked out again from where the words are said now, then the cut made again."""
    from app import cut, cut_edits

    if choice["do"] == "cut_away":
        span = _away_span(db, project, ask.subject)
        kind, asked = "presenter", (span and {"start": span[0], "end": span[1], "hidden": True})
    else:
        edit = _pause_edit(db, project, ask.subject)
        kind, asked = "trim", (edit and edit[0])
    if not asked:
        raise HTTPException(409, "The cut doesn't say those words where it did: make the cut "
                            "again first, or change it in the cut editor.")  # fmt: skip
    try:
        row = cut_edits.add(db, user, project, kind, asked)
    except cut.Refused as no:
        db.rollback()
        raise HTTPException(409, str(no)) from no
    db.commit()
    said, made = _make_cut(db, project, user, storage)
    return {"edit": row.id, "outcome": f"Done. {said}", "cut": made}


def _make_cut(db: Session, project: Project, user: User, storage) -> tuple[str, bool]:
    """The next cut, free (cut.make's own route); or plainly why not."""
    from app.routes import cut

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    try:
        made = cut.make(project_id=project.id, request=request, user=user, db=db)
    except HTTPException as no:
        db.rollback()
        return (f"The cut wasn’t made again: {no.detail} Make the cut from the Cut tab once "
                "that’s done.", False)  # fmt: skip
    return f"Making Cut {made.making.number if made.making else made.number} with it.", True


def _change_line(db: Session, user: User, project: Project, ask: Ask, choice: dict,
                 storage) -> dict:  # fmt: skip
    from app import line_change

    return line_change.press(db, user, project, ask, choice, storage)


def _owner_only() -> str:
    from app import line_change

    return line_change.OWNER_ONLY


DOES = {"softer": _say_softer, "cut_away": _edit_the_cut, "pause": _edit_the_cut,
        "change_line": _change_line}  # its press  # fmt: skip


def after(db: Session, job: Job, storage) -> None:
    """A choice's take, or its watch, finished: once the take's watch is back (and a remake its
    watch made is watched in turn), its clip is approved and the cut made again if it's clean;
    else the card says what was found and the cut stays as it was."""
    take = _take(db, job)
    if take is None:
        return
    root = _root(db, take)
    mark = (db.get(Job, root.job_id).input.get(FOR) if root and root.job_id else None) or []
    ask = db.get(Ask, mark[0]) if mark else None
    if ask is None or ask.kind != KIND:
        return
    watch = take.watch or {}
    if watch.get("state") == "watching" or watch.get("action") in ("redo", "held"):
        return  # its watch comes next, or its watch is remaking it: wait for that
    project = db.get(Project, ask.project_id)
    n = db.get(ProjectClip, take.clip_id).clip_id.removeprefix("c")
    found = (watch.get("did") or "It wasn't watched.").rstrip(".")
    if watch.get("state") in ("skipped", "failed") or not watch:  # not watched: the person's call
        _outcome(db, ask, mark[1], f"Made. {found}, so the cut stays as it was. Use take "
                 f"{take.number} and make the cut, or look at it in Clips first.", cut=False,
                 use=take.id)  # fmt: skip
        return
    if watch.get("action") != "keep":  # its watch found something: the owner looks first
        _outcome(db, ask, mark[1], f"Made. {found}. The cut stays as it was; look at clip "
                 f"{n} in Clips, then make the cut.", cut=False)  # fmt: skip
        return
    said, cut = _cut(db, project, take, storage)
    _outcome(db, ask, mark[1], said, cut=cut)


def _take(db: Session, job: Job) -> ClipTake | None:
    """The take a finished job is about: a take it made, or the take its watch looked at."""
    if job.kind == "video":
        return db.scalar(select(ClipTake).where(ClipTake.job_id == job.id))
    take_id = job.input.get("take_id") or (job.input.get("watch") or {}).get("take_id")
    return db.get(ClipTake, take_id) if take_id else None


def _root(db: Session, take: ClipTake) -> ClipTake | None:
    """The take a chain of the watch's remakes started from (each remake names the one before)."""
    from app.take_watch import REDO

    seen = set()
    while take is not None and take.id not in seen:
        seen.add(take.id)
        job = db.get(Job, take.job_id) if take.job_id else None
        if job is None or not job.input.get(REDO):
            return take
        take = db.get(ClipTake, job.input[REDO])
    return take


def _cut(db: Session, project: Project, take: ClipTake, storage, user: User | None = None,
         chosen: bool = False) -> tuple[str, bool]:  # fmt: skip
    """That clip approved (only it) and the next cut started, free; or plainly why not. Its
    watch came back clean, or a person chose the take (`chosen`: their OK, rule 21). A clip
    someone has since put on another take keeps it: the cut isn't made over their pick."""
    from app.routes import cut, project_clips

    row = db.get(ProjectClip, take.clip_id)
    n = row.clip_id.removeprefix("c")
    if not chosen and row.picked_take_id != take.id:
        return (f"Made and watched, but clip {n} now uses another take, so the cut stays as "
                "it was.", False)  # fmt: skip
    user = user or db.get(User, db.get(Job, take.job_id).created_by_id)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    me = {"project_id": project.id, "user": user, "db": db}
    done = f"Take {take.number} is used" if chosen else "Made and watched"
    try:
        if row.picked_take_id != take.id:
            project_clips.pick_take(clip_id=row.id, take_id=take.id, **me)
        row.approved = True  # this clip only: its watch came back clean, or a person chose it
        db.flush()
        made = cut.make(request=request, **me)  # on the worker; a failed one says why in Cut
    except HTTPException as no:
        db.rollback()
        return (f"{done}, but the cut wasn’t made again: {no.detail} Make the cut from the Cut "
                "tab once that’s done.", False)  # fmt: skip
    return f"{done}. Making Cut {made.making.number if made.making else made.number} with it.", True


def _outcome(db: Session, ask: Ask, key: str, said: str, cut: bool,
             use: int | None = None) -> None:  # fmt: skip
    ask = db.get(Ask, ask.id)
    chosen = dict((ask.answer or {}).get("chosen") or {})
    chosen[key] = {**chosen.get(key, {}), "outcome": said, "cut": cut, "use": use}
    ask.answer = {**(ask.answer or {}), "chosen": chosen}
    db.commit()
