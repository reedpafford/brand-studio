"""The talker. A UGC presenter who talks to camera full screen is filmed on Omni 1.2 speaking
for themself (Reed, 9 Nov; `omni`, `cutaways`). A presenter who talks to camera in another
style (Reed, 3 Nov: "Heygen for still imaged UGC talking, yes.") isn't keyed into a corner: one
still of the talker in their own room, then ONE HeyGen Avatar IV take of the whole narration
(the voice picked at their audition, app/audition.py, with its room sound, app/room.py),
lip-synced from that still (app/host.py makes both, priced like takes). The plan's talker
shots (in a narration, `sung`: the talker says that stretch to the lens) are cut from that take
at the final cut; every other shot is B-roll cut in over the voice, so the cut alternates
talker and B-roll. Settings from HeyGen's docs and the paid tests (batch-b,
.context/team/research/ugc-realism.md; th-20s, .context/tests/th-20s/REPORT.md; 293,
team/round2/UGC-DIAGNOSIS.md): type image, 720p, expressiveness from the read's mood
(`expressiveness`), and a motion prompt the director writes for this narration's emotion and
lines (`motion`), every take keeping its eyes on the lens (`LENS`) and nobody else in it
(`ALONE`). 293 (high, a light confession, no hands named) shut or squinted the eyes in about
40% of its frames and moved a third as much as the references; batch-b (medium, a hand
gesture named) moved like a phone talker. th-20s's "hand gesture low in the frame" popped a
stray hand in by the steering wheel, so hands come up at chest height."""

import hashlib
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import narration
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project

LOOKS = ("ugc",)  # styles whose host talks in their own room, not keyed in a corner
MODEL, RESOLUTION, PROVIDER = "heygen-avatar-iv", "720p", "heygen"
LONGEST = 600.0  # HeyGen: an avatar's audio input runs 10 minutes at most
FIT = 1920  # HeyGen takes images under 2K: "as much resolution as you have"
STILL_PROMPT = (
    "{who}, filmed by themselves on their phone: chest-up, centred, facing the camera at eye "
    "level and looking straight into the lens, the whole head and both shoulders in frame with "
    "a little space above the head, a relaxed, natural expression, the mouth closed or just "
    "parted. Nothing covers the face: no sunglasses, no hat brim, no hand near the mouth. They "
    "are {where}, in focus behind them, lit by soft daylight from the front. A real vertical "
    "phone photo, unretouched: natural skin with pores, no studio light, no shallow-focus blur, "
    "only this one person in it, alone in the frame."
)  # HeyGen: a clear, front-facing, evenly lit portrait, the whole head in frame, one person
ROOM = "in their own real, lived-in room that says who they are"  # with no plan to say where
EXPRESSIVENESS = "high"  # HeyGen: high, medium or low ("energy and range of movement"); on green
# The moods a whole read is in that move the face a lot (th-20s: a crying mother, high);
# any other read is medium (`expressiveness`)
BIG = ("sad", "fearful", "angry")
MOTION = (
    "They stay where they are and talk straight into the phone lens like a real selfie video, "
    "telling a friend something: easy head nods and tilts, the shoulders shifting as they talk, "
    "and their hands coming up at chest height to gesture on the key words, then dropping "
    "away. The camera stays locked off the whole time."
)  # when the director writes none (Make the host pressed by a person)
# Every talker take, after the note: the eyes on the lens (the UGC guide's must keep; 293's
# wince), and alone; said as what is there, never as what isn't (#1392's HeyGen notes: a
# negative can suggest it; 281's strangers)
LENS = "Their eyes stay open on the lens after any glance, the brow easy, blinking normally."
ALONE = ("They are alone in the frame the whole time; the place behind them stays exactly as "
         "the picture shows it, still and empty.")  # fmt: skip
LONGEST_MOTION = 600  # characters: a motion note is a few sentences
SAID = ("The talker says this clip: its picture is cut from the talker's take. To change how "
        "the talker looks or where they are, press Make it again on the presenter in the "
        "Cast tab: their still is drawn again and their take made from it.")  # fmt: skip
NO_SHOTS = ("The plan has no talker shots, so the talker would never be seen. Plan again with "
            "the talker on screen for the hook, the turns and the close.")  # fmt: skip
TOO_LONG = "The narration runs past HeyGen's 10 minutes. Shorten the script to make the talker."


def on(db: Session, project: Project) -> bool:
    """A Presenter video whose presenter talks to camera in their own room on HeyGen (chosen
    for a video in a style other than UGC: app/host.how; a UGC one is `omni`)."""
    from app import host

    return host.on(db, project) and host.how(project) == "talks"


def full_screen(look: str | None, presenter: str | None) -> bool:
    """A UGC presenter who talks to camera filling the frame (the style's start), not in a
    corner over the B-roll and not acting in the story (app/host.HOW)."""
    from app import host, looks

    how = presenter if presenter in host.HOW else "talks"
    return looks.base(look or looks.DEFAULT) in LOOKS and how == "talks"


def films(script, video=None) -> bool:
    """`omni` for a script's quote: its own look before it has a video. A video whose voice
    track was made before this (a narration in use) keeps its HeyGen talker."""
    from app import host

    if video is not None and video.song_take_id:
        return False
    shown = (video.look, video.presenter) if video is not None else (script.look, None)
    return host.hosted(script) and full_screen(*shown)


def omni(db: Session, project: Project) -> bool:
    """A Presenter video whose UGC presenter talks to camera full screen, filmed on Omni 1.2
    (Reed, 9 Nov: "Full screen UGC should be omni, yes. Meaning the talking head is filmed in
    omni"): a story video whose talker says the script's lines in their own Omni pieces, lips,
    voice and room from one take, with no voice-over and no HeyGen take, and whose B-roll is
    laid over their picture, silent, while their voice runs on (`cutaways`). A corner
    presenter stays one HeyGen take of our voice track (app/host.py)."""
    return films(narration.video_script(db, project), project)


PIECE = ("{who} is the presenter and talks straight to camera, filling the frame, filmed on "
         "Omni 1.2 in pieces of their own: every spoken line is theirs, said on camera, a line "
         "with no speaker label too. Their shots have `speaker` \"{who}\", the line's exact words "
         "in `line` and {who} in `character_ids`. Their consecutive shots in one place share one "
         "clip of up to {most} s, in script order: as few pieces as the lines allow, so a talker "
         "sitting in one spot is never split into short pieces without a reason (a new place, a "
         "real change of shot). Their clips alone make the video's length.\n"
         "B-roll is cut in over their voice, never between their pieces: a B-roll shot shows "
         "what a line says, names that line in `script_lines`, and has no `line` or `speaker` "
         "(nobody speaks in it: their voice runs on under it). A talker clip's B-roll shots "
         "come right after it, in clips of their own, in the order of the words they show; the "
         "cut lays each over the talker's picture where its line is said.")  # fmt: skip


def breakdown_block(db: Session, project: Project, most: int) -> str:
    """How an Omni talker's plan is laid out (`omni`), for the breakdown step: named as
    their look is, else as the script's first speaker label names them."""
    from app import host
    from app.prompts.check import LABEL
    from app.routes.scripts import latest

    item, words = host.host_look(db, project), latest(db, project)
    said = next((m[1] for x in (words.text if words else "").splitlines()
                 if (m := LABEL.match(x))), "")  # fmt: skip
    who = item.name if item else said.title() or "The presenter"
    return f"<talker>\n{PIECE.format(who=who, most=most)}\n</talker>"


def _plan(data: dict) -> list[tuple[str, list[dict]]]:
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    return [(c["id"], [shots[i] for i in c.get("shot_ids", []) if i in shots])
            for c in data.get("clips", [])]  # fmt: skip


def fewer(data: dict, most: int) -> list[str]:
    """Advice on an Omni talker's plan: two of their pieces in one spot, with only B-roll
    between them, that one piece of up to `most` s holds (Reed: real UGC scripts run 3-4
    minutes; a sitting talker isn't split without a reason)."""
    from app import one_frame
    from app.prompts.check import ADVICE

    lead = one_frame.followers(data, True, False)
    seconds = {c["id"]: c.get("seconds") or 0 for c in data.get("clips", [])}
    talks = [c for c, mine in _plan(data) if any(s.get("line") for s in mine)]
    return [f"{ADVICE}clips {a} and {b}: the talker in one spot, {seconds[a] + seconds[b]} s "
            "together; make them one piece" for a, b in zip(talks, talks[1:], strict=False)
            if lead.get(a, a) == lead.get(b, b) and seconds[a] + seconds[b] <= most]  # fmt: skip


def cutaways(db: Session, project: Project, rows: list[ProjectClip]) -> list[dict]:
    """An Omni talker video's B-roll clips, each laid over the talker's piece that says the
    first line it shows, from where that line starts: its first word as the piece's words
    check heard it, else its share of the piece's words. [{clip_id, take_id, piece, at,
    seconds}], `at` in seconds into the piece's take, `seconds` the B-roll take's own."""
    from app.clip_prompts import newest
    from app.cut import _take_seconds
    from app.word_splice import _heard

    plan = _plan(bd.data if (bd := newest(db, project)) else {})
    said: dict[int, tuple[str, int]] = {}  # a script line -> its talker clip, words before it
    for cid, mine in plan:
        k = 0
        for s in (s for s in mine if s.get("line")):
            said.update({n: (cid, k) for n in s.get("script_lines") or [] if n not in said})
            k += len(s["line"].split())
    picked = {r.clip_id: r for r in rows}
    out = []
    for cid, mine in plan:
        n = next((x for s in mine for x in s.get("script_lines") or [] if x in said), None)
        row, (talk, k) = picked.get(cid), said.get(n, ("", 0))
        voice = picked.get(talk)
        if any(s.get("line") for s in mine) or not (row and row.picked_take_id and voice):
            continue
        take = db.get(ClipTake, voice.picked_take_id) if voice.picked_take_id else None
        heard = _heard(db, take)[0] if take else []
        words = sum(len(s["line"].split()) for s in dict(plan)[talk] if s.get("line"))
        at = heard[k]["start"] if k < len(heard) else voice.seconds * k / max(words, 1)
        out.append({"clip_id": cid, "take_id": row.picked_take_id, "piece": talk,
                    "at": round(at, 2), "seconds": _take_seconds(
                        db, db.get(ClipTake, row.picked_take_id), row.seconds)})  # fmt: skip
    return out


def minimax(db: Session, project: Project) -> bool:
    """A UGC presenter in one spot the whole time, talking to camera or in a corner over the
    B-roll (Reed, 6 Nov: a talker in one spot is HeyGen with our MiniMax voice): someone
    filming themselves, whose voice reads run together as they'd say it (app/audition.py)."""
    from app import host, looks

    ugc = looks.base(project.look or looks.DEFAULT) in LOOKS
    return on(db, project) or (ugc and host.on(db, project))


def _spoken(data: dict, clip_id: str) -> bool:
    """Every shot of the clip is a talker shot (`sung` on the narration's clock)."""
    timed = (data.get("song") or {}).get("shots") or {}
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == clip_id), [])
    return bool(ids) and all(timed.get(s, {}).get("sung") for s in ids)


def clips(db: Session, project: Project) -> set[str]:
    """The newest plan's talker clips: they take no take of their own."""
    from app.clip_prompts import newest

    bd = newest(db, project) if on(db, project) else None
    data = bd.data if bd else {}
    return {c["id"] for c in data.get("clips", []) if _spoken(data, c["id"])}


def where(db: Session, project: Project) -> str:
    """Where the plan puts the talker (video 281: the still said "their own room" and HeyGen
    made all three tries in a home office, for "Marcus in his parked car"): the scene of their
    first clip, its heading and its look; ROOM with none."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    data = bd.data if bd else {}
    mine = clips(db, project)
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] in mine), [])  # first
    scene = next((sc for sc in data.get("scenes", []) for s in sc.get("shots", [])
                  if ids and s["id"] == ids[0]), None)  # fmt: skip
    if scene is None:
        return ROOM
    look = (scene.get("look") or "").strip()
    return f"where the plan puts them, {scene.get('heading', '').strip()}: {look}"[:400]


# Inside a vehicle, never just a vehicle word ("car keys on the counter", "my car insurance",
# "the food truck", "a Van Gogh print"): in/inside a car, truck or SUV, a car seat's or
# wheel's words, or a heading "INT. ... CAR" (QA on #1477)
CAR = re.compile(
    r"\b(?:in|inside|into)\s+(?:the|a|an|her|his|their|my|our|your)\s+(?:[\w'-]+\s+){0,3}?"
    r"(?:car|truck|suv)\b(?!\s*(?:insurance|keys?|payments?|loans?|wash|dealer\w*|park)\b)"
    r"|\b(?:driver'?s|passenger)\s+seat\b|\bsteering wheel\b|\bseat\s?belt\b"
    r"|\bINT\.[^\n:]*?\b(?:CAR|TRUCK|SUV)\b",
    re.I,
)


def place(db: Session, project: Project) -> str:
    """Where the talker's voice was recorded, for its sound (room.PLACES): "car" when where
    they film themselves is a vehicle (the plan's place, else the treatment's hook, written
    before the voice is made), else "room"."""
    from app.director import treatment

    said = where(db, project)
    if said == ROOM:
        said = str((treatment(db, project) or {}).get("hook") or "")
    return "car" if CAR.search(said) else "room"


def frame(db: Session, project: Project) -> int | None:
    """The drawn still of the talker's first clip: where the plan puts them, as drawn."""
    from app.clip_prompts import newest
    from app.models.storyboards import StoryboardFrame

    bd, mine = newest(db, project), clips(db, project)
    first = next((c["id"] for c in (bd.data if bd else {}).get("clips", []) if c["id"] in mine),
                 None)  # fmt: skip
    return db.scalar(select(StoryboardFrame.file_id).where(
        StoryboardFrame.project_id == project.id, StoryboardFrame.breakdown_id == bd.id,
        StoryboardFrame.clip_id == first, StoryboardFrame.file_id.is_not(None))
        .order_by(StoryboardFrame.id).limit(1)) if first else None  # fmt: skip


def shot(db: Session, project: Project, shot_id: str) -> bool:
    """The shot is the talker's (one of their clips'): its picture is the talker's still."""
    from app.clip_prompts import newest

    bd, mine = newest(db, project), clips(db, project)
    return any(shot_id in c["shot_ids"] for c in (bd.data if bd else {}).get("clips", [])
               if c["id"] in mine)  # fmt: skip


def says(db: Session, project: Project, clip: ProjectClip) -> bool:
    from app.models.breakdowns import BreakdownVersion

    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    return bool(bd) and on(db, project) and _spoken(bd.data, clip.clip_id)


def share(db: Session, project: Project) -> dict:
    """What the director reads: the talker clips, the talker's share of the screen and the
    longest stretch of talker without a cut-in (the references: 40-47% and median holds of
    3-6 s)."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    timed = ((bd.data if bd else {}).get("song") or {}).get("shots") or {}
    spans = sorted((t["start"], t["end"], bool(t.get("sung"))) for t in timed.values())
    total = max((b for _, b, _ in spans), default=0) or 1
    holds, run = [], 0.0
    for a, b, sung in spans:
        run = run + b - a if sung else 0.0
        holds.append(run)
    talking = sum(b - a for a, b, sung in spans if sung)
    return {"clips": sorted(clips(db, project)), "on_screen": round(talking / total, 2),
            "longest_hold": round(max(holds, default=0), 1)}  # fmt: skip


def whole(seconds: float) -> list[tuple[float, float]]:
    """The talker's one piece: the whole narration, within HeyGen's 10 minutes."""
    if seconds > LONGEST:
        raise ValueError(TOO_LONG)
    return [(0.0, seconds)]


def motion(note: str) -> str:
    """The director's motion note for the take (its emotion and lines: what the face, head and
    hands do, and what's in front of them), else the plain one."""
    return " ".join((note or "").split())[:LONGEST_MOTION] or MOTION


def expressiveness(db: Session, project: Project) -> str:
    """HeyGen's range for the talker: high for a narration read in one big mood (BIG), else
    medium, so a light read doesn't wince (293, auto: eyes shut or squinting in 40% of frames)."""
    from app.models.jobs import Job
    from app.models.songs import SongTake

    take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    made = db.get(Job, take.job_id) if take and take.job_id else None
    return "high" if made and narration.delivery(made.input).get("emotion") in BIG else "medium"


def piece_input(project: Project, row, still_file_id: int, note: str = "",
                how: str = EXPRESSIVENESS) -> dict:  # fmt: skip
    """The one HeyGen take: the still, and the whole narration as the voice it lip-syncs
    (`duration` is for the stand-in; HeyGen's length follows the voice). `note`: the
    director's motion note (kept in the job's input, `motion`, for a remake); `how`: its
    expressiveness."""
    from app import host

    return {"step": host.PIECE, "project_id": project.id, "host_piece_id": row.id,
            "model": MODEL, "brand_id": project.brand_id, "fit_images_to": FIT,
            "input": {"aspect_ratio": project.aspect_ratio, "resolution": RESOLUTION,
                      "expressiveness": how, "motion_prompt": motion(note),
                      "title": f"Brand Studio video {project.id}",
                      "duration": host._seconds(row)},
            "files": {"image": [still_file_id], "audio": [row.audio_file_id]}}  # fmt: skip


def _segment(video: bytes, start: float, end: float) -> bytes:
    """The talker's take from `start` to `end`, picture only (the narration is the sound)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        command = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", "in.mp4", "-t",
                   f"{max(end - start, 0.1):.3f}", "-an", "-c:v", "libx264", "-pix_fmt",
                   "yuv420p", "-movflags", "+faststart", "out.mp4"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=300)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()


def fill(db: Session, storage, project: Project) -> None:
    """Each talker clip's take, cut from the talker's one take (free: ffmpeg), picked and
    approved; cut again only when the talker's take is a new one."""
    from app import host, video_settings

    piece = next(iter(host.rows(db, project)[1:]), None)
    made = host._jobs(db, project).get(piece.id) if piece and piece.file_id else None
    if made is None:
        return
    whole = None
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        picked = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
        done = picked and (picked.made_with or {}).get("talker") == piece.file_id
        if done or not row.song_slice or not says(db, project, row):
            continue
        whole = whole or storage.get(db.get(StoredFile, piece.file_id).key)
        part = _segment(whole, row.song_slice["start"], row.song_slice["end"])
        key = f"{project.workspace_id}/{uuid.uuid4().hex}"
        storage.put(key, part)
        stored = StoredFile(workspace_id=project.workspace_id, key=key, size=len(part),
                            filename=f"talker {row.clip_id}.mp4", content_type="video/mp4",
                            sha256=hashlib.sha256(part).hexdigest())  # fmt: skip
        db.add(stored)
        db.flush()
        number = db.scalar(select(func.max(ClipTake.number)).where(ClipTake.clip_id == row.id))
        sung = row.song_slice.get("sung_shots")
        take = ClipTake(clip_id=row.id, number=(number or 0) + 1, job_id=made.id,
                        file_id=stored.id, prompt=row.prompt, look=project.look,
                        made_with={**video_settings.made_with(db, project, [], MODEL, sung),
                                   "talker": piece.file_id})  # fmt: skip  # made on HeyGen
        db.add(take)
        db.flush()
        row.picked_take_id, row.file_id, row.approved = take.id, stored.id, True
    db.flush()
