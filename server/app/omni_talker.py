"""A UGC presenter who talks to camera full screen, filmed on Omni 1.2 (Reed, 9 Nov: "Full
screen UGC should be omni, yes. Meaning the talking head is filmed in omni"). The video is a
story video: the talker says the script's lines on camera in their own Omni pieces, lips, voice
and room from one take, with no voice-over, no voice audition and no HeyGen take. Their voice is
described once and said word for word in every piece (`voice`, voices.on_omni), every piece
opens on their one still at rest (app/one_frame.py), and their B-roll is made silent and laid
over their picture where its line is said while their voice runs on (`cutaways`, cut.laid_over).
A corner presenter stays one HeyGen take of our voice track (app/host.py, app/talker.py)."""

import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app import narration
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.songs import SongTake
from app.talker import LOOKS  # the styles whose presenter talks to camera by default

NAMED = "The presenter"  # the talker's name with no speaker label and no look
VOICE = "the natural everyday voice of {who}, close to the phone, the same in every piece"
# A piece sized to its words (Reed, 9 Nov, the UGC playbook §3): words a second, a slow line's,
# and the room after them. A short line in a long piece drags its words and pauses oddly.
PACE, SLOW, ROOM = 2.6, 2.1, 1.0
END = re.compile(r"[.!?…][\"'”’)\]]*$")  # a sentence's last word


def full_screen(look: str | None, presenter: str | None) -> bool:
    """A UGC presenter who talks to camera filling the frame (the style's start), not in a
    corner over the B-roll and not acting in the story (app/host.HOW)."""
    from app import host, looks

    how = presenter if presenter in host.HOW else "talks"
    return looks.base(look or looks.DEFAULT) in LOOKS and how == "talks"


def films(script, video=None) -> bool:
    """`on` for a script's quote: its own look before it has a video. A video with a narration
    of its own, in use or not (one made before this, one read again for a changed line, one
    turned down), keeps its HeyGen talker: its engine never flips (QA on #1497)."""
    from app import host

    shown = (video.look, video.presenter) if video is not None else (script.look, None)
    if not (host.hosted(script) and full_screen(*shown)):
        return False
    return video is None or not (video.song_take_id or _narrated(video))


def _narrated(video) -> bool:
    db = object_session(video)
    own = select(SongTake.id).where(SongTake.project_id == video.id,
                                    SongTake.kind == narration.KIND)  # fmt: skip
    return bool(db and video.id) and db.scalar(own.limit(1)) is not None


def on(db: Session, project: Project) -> bool:
    """A Presenter video whose UGC presenter talks to camera full screen, filmed on Omni."""
    return films(narration.video_script(db, project), project)


def name(db: Session, project: Project) -> str:
    """The talker as the treatment, the plan and the clips all name them: the script's first
    speaker label, else their look's name, else NAMED."""
    from app import host
    from app.prompts.check import LABEL
    from app.routes.scripts import latest

    words = latest(db, project)
    said = next((m[1] for x in (words.text if words else "").splitlines()
                 if (m := LABEL.match(x))), "")  # fmt: skip
    item = None if said else host.host_look(db, project)
    return said.title() or (item.name if item else NAMED)


def treatment_block(db: Session, project: Project) -> str:
    """The treatment hears that the presenter speaks on camera, so its `voices` names them."""
    who = name(db, project)
    return (f"<talker>\n{who} is the presenter, filmed talking straight to camera: they say "
            "every line of the script on camera in their own voice (Omni 1.2's; there is no "
            f"voice-over), so `voices` names them, as \"{who}\".\n</talker>")  # fmt: skip


def voice(db: Session, project: Project, sounds: list) -> tuple[list[str], str] | None:
    """The talker's voice when neither a saved voice nor a treatment set one (`sounds`, as
    voices.on_omni found them): from their look's own description, so every piece still
    repeats one voice line, never none."""
    from app import host, voices

    if not on(db, project) or voices.voice_of(who := name(db, project), sounds):
        return None
    item = host.host_look(db, project)
    told = ((item.notes or item.short_description or "") if item else "").strip().rstrip(".")
    said = told[:1].lower() + told[1:] if told else "someone filming themself on their phone"
    names = [who, *([item.name] if item else []), NAMED]
    return list(dict.fromkeys(names)), voices._cut(VOICE.format(who=said))


PIECE = ("{who} is the presenter and talks straight to camera, filling the frame, filmed on "
         "Omni 1.2 in pieces of their own: every spoken line is theirs, said on camera, a line "
         "with no speaker label too. Their shots have `speaker` \"{who}\", the line's exact words "
         "in `line` and {who} in `character_ids`. Their consecutive shots in one place share one "
         "clip of up to {most} s, in script order: as few pieces as the lines allow, so a talker "
         "sitting in one spot is never split into short pieces without a reason (a new place, a "
         "real change of shot). Their clips alone make the video's length.\n"
         "A piece ends only where one of the script's sentences ends, never mid-sentence or at a "
         "comma: a piece cut on a comma ends on a falling tone and the join is heard. Size each "
         "piece to its words: about 2.6 words a second (2.1 for a slow, heavy line) plus about "
         "1 s, so 24 words make about 10 s. Their words are the script's and nothing more: never "
         "a filler (\"Okay.\", \"um\") to pad a short piece.\n"
         "B-roll is cut in over their voice, never between their pieces: a B-roll shot shows "
         "what a line says, names that line in `script_lines`, and has no `line` or `speaker` "
         "(nobody speaks in it: their voice runs on under it). A talker clip's B-roll shots "
         "come right after it, in clips of their own, in the order of the words they show; the "
         "cut lays each over the talker's picture where its line is said.")  # fmt: skip


def breakdown_block(db: Session, project: Project, most: int) -> str:
    """How an Omni talker's plan is laid out, for the breakdown step."""
    return f"<talker>\n{PIECE.format(who=name(db, project), most=most)}\n</talker>"


def _plan(data: dict) -> list[tuple[str, list[dict]]]:
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    return [(c["id"], [shots[i] for i in c.get("shot_ids", []) if i in shots])
            for c in data.get("clips", [])]  # fmt: skip


def _talks(shots: list[dict]) -> bool:
    return any(s.get("line") for s in shots)


def fewer(data: dict, most: int) -> list[str]:
    """Advice on the plan: two of the talker's pieces in one spot, with only B-roll between
    them, that one piece of up to `most` s holds (Reed: real UGC scripts run 3-4 minutes; a
    sitting talker isn't split without a reason)."""
    from app import one_frame
    from app.prompts.check import ADVICE

    lead = one_frame.followers(data, True, False)
    seconds = {c["id"]: c.get("seconds") or 0 for c in data.get("clips", [])}
    talks = [c for c, mine in _plan(data) if _talks(mine)]
    return [f"{ADVICE}clips {a} and {b}: the talker in one spot, {seconds[a] + seconds[b]} s "
            "together; make them one piece" for a, b in zip(talks, talks[1:], strict=False)
            if lead.get(a, a) == lead.get(b, b) and seconds[a] + seconds[b] <= most]  # fmt: skip


def _plain(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower().replace("’", "'"))


def _whole(line: str, script: str) -> bool:
    """`line` ends where one of the script's sentences ends (a full stop, ? or !, or the end of
    a script line), wherever the script says those words; True when it can't tell."""
    from app.prompts.check import narration_text

    said = [(_plain(w), bool(END.search(w)) or i == len(ws) - 1)
            for x in narration_text(script).splitlines()
            for ws in [x.split()] for i, w in enumerate(ws)]  # fmt: skip
    mine, n = [_plain(w) for w in line.split()], len(line.split())
    found = [said[i + n - 1][1] for i in range(len(said) - n + 1)
             if [w for w, _ in said[i:i + n]] == mine]  # fmt: skip
    return not found or any(found)


def pieces(bd, script: str, least: int, most: int):
    """The talker's pieces to Reed's 9 Nov rules (the UGC playbook §3): each sized to its words,
    between PACE and SLOW plus ROOM and any wordless hold it has, within the model's `least` to
    `most` s (free, said as Advice); a fix for a piece that ends mid-sentence, or whose words
    need more than one piece. (Breakdown, what it found)."""
    from app.prompts.check import ADVICE

    bd, found, sized = bd.model_copy(deep=True), [], []
    shots = {s.id: s for sc in bd.scenes for s in sc.shots}
    for clip in bd.clips:
        mine = [shots[i] for i in clip.shot_ids if i in shots]
        said = [s.line for s in mine if s.line]
        if not said:
            continue
        if not _whole(said[-1], script):
            found.append(f"clip {clip.id}: the talker's piece stops mid-sentence (“…"
                         f"{' '.join(said[-1].split()[-4:])}”); end each piece where a sentence "
                         "ends, never at a comma")  # fmt: skip
        words = sum(len(x.split()) for x in said)
        held = sum(s.seconds for s in mine if not s.line)
        low, high = (math.ceil(words / pace + ROOM + held - 0.01) for pace in (PACE, SLOW))
        if low > most:  # never squeezed: too long, it's split (the breakdown's Split fix)
            found.append(f"clip {clip.id}: its {words} words need about {low} s, more than one "
                         f"piece's {most} s; split it where a sentence ends")  # fmt: skip
            continue
        to = max(least, min(most, high, max(low, clip.seconds)))
        if to != clip.seconds and (total := sum(s.seconds for s in mine)):
            for s in mine:
                s.seconds = round(s.seconds * to / total, 1)
            mine[-1].seconds = round(to - sum(s.seconds for s in mine[:-1]), 1)
            clip.seconds, sized = to, [*sized, clip.id]
    if sized:
        found.append(f"{ADVICE}The talker's pieces {', '.join(sized)} are sized to their words: "
                     "about 2.6 words a second, 2.1 for a slow line, plus 1 s.")  # fmt: skip
    return bd, found


def most_seconds(words: int, most: int) -> int:
    """The talker's pieces at the most they're sized to (rule 36's "up to"): every word at a
    slow line's pace, plus ROOM for each piece of up to `most` s."""
    said = words / SLOW
    return math.ceil(said + ROOM * math.ceil(said / (most - ROOM)))


def cutaways(db: Session, project: Project,
             rows: list[ProjectClip]) -> tuple[list[dict], set[str]]:  # fmt: skip
    """The plan's B-roll clips, and each one made laid over a talker piece: the piece that says
    the first line it shows, from where that line starts (its first word as the piece's words
    check heard it, else its share of the piece's words); one whose line no piece says goes over
    the nearest piece before it, ending with its last word (else the next, from its start),
    never a silent stretch of its own. ([{clip_id, take_id, piece, at, seconds}], the B-roll
    clip ids): `at` in seconds into the piece's take, `seconds` the B-roll take's own."""
    from app.clip_prompts import newest
    from app.cut import _take_seconds
    from app.word_splice import _heard

    plan = _plan(bd.data if (bd := newest(db, project)) else {})
    talks = [cid for cid, mine in plan if _talks(mine)]
    said: dict[int, tuple[str, int]] = {}  # a script line -> its talker clip, words before it
    for cid, mine in plan:
        k = 0
        for s in (s for s in mine if s.get("line")):
            said.update({n: (cid, k) for n in s.get("script_lines") or [] if n not in said})
            k += len(s["line"].split())
    picked, out = {r.clip_id: r for r in rows}, []
    for i, (cid, mine) in enumerate(plan):
        row = picked.get(cid)
        if cid in talks or not (row and row.picked_take_id):
            continue
        n = next((x for s in mine for x in s.get("script_lines") or [] if x in said), None)
        before = [c for c, _ in plan[:i] if c in talks][-1:]
        if n:
            talk, k = said[n]
        else:  # no piece says its line: the nearest piece before it, else the one after
            after = [c for c, _ in plan[i:] if c in talks][:1]
            talk, k = (before or after or [""])[0], None
        voice = picked.get(talk)
        if voice is None or not voice.picked_take_id:
            continue
        heard = _heard(db, db.get(ClipTake, voice.picked_take_id))[0]
        seconds = _take_seconds(db, db.get(ClipTake, row.picked_take_id), row.seconds)
        if k is not None:
            words = sum(len(s["line"].split()) for s in dict(plan)[talk] if s.get("line"))
            at = heard[k]["start"] if k < len(heard) else voice.seconds * k / max(words, 1)
        else:  # over the end of the piece before it, or the start of the one after
            last = heard[-1]["end"] if heard else float(voice.seconds)
            at = max(0.0, last - seconds) if before else 0.0
        out.append({"clip_id": cid, "take_id": row.picked_take_id, "piece": talk,
                    "at": round(at, 2), "seconds": seconds})  # fmt: skip
    return out, {cid for cid, _ in plan if cid not in talks}
