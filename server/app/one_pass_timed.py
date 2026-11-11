"""The one-pass director on a recorded track (app/one_pass.py): a Narrated, Zack D, Presenter
or Song video is timed to its narration or song, made and measured before the plan. The plan
says only the second each shot starts (`at`) and what each clip is (`kind`); everything else is
worked out here, with no model call: `at` lands on the nearest measured start (`snapped`), a
shot ends where the next begins, a clip too long to make is cut at a shot's edge (`packed`),
each shot carries the script lines heard under it (`clock`), and the plan's times become the
song part every later step reads (`song_part`: song_breakdown's own, so the takes' lengths and
slices, the silent B-roll, the talker's clips and the cut all work as they do today)."""

from sqlalchemy.orm import Session

from app import narration, song_breakdown
from app.models.projects import Project
from app.prompts import check, unnoted
from app.prompts.schemas import PlanClip, ShootingPlan

BROLL, HOST = "broll", "host"  # a timed clip's kinds: silent picture, or the talker to the lens
SHORTEST = 1.0  # seconds: a shot's least, so its clip's prompt can time it in whole seconds
SHORT = ("clip {c} shot {n} runs from {at:.2f} s to {end:.2f} s of the track, under a second: "
         "start each shot at least a second after the one before it and before the track "
         "ends, on a sentence's or a word's own start from <song>")  # fmt: skip
TOO_LONG = ("clip {c} shot {n} runs {s:.1f} s, and this video model makes {most} s a clip at "
            "most: start another shot inside it, on a word's start from <song>")  # fmt: skip


# How a Presenter video's presenter appears (app/host.HOW), said to the plan call in the user
# message: a choice made for each video, so never part of the cached prompt.
HOSTS = {
    "corner": (
        "{who} presents this video from a bottom corner of the frame, laid over the "
        "pictures once they are made, and is never in a shot or in `people`: every clip "
        "is B-roll. Keep each shot's action in the upper two-thirds with the bottom "
        'corners clear. Where the action sits on the right of the frame, say "on the '
        "right\" in that shot's `action`, so the host stands on the left there."
    ),
    "talks": (
        "{who} presents this video, talking to camera in the one place they film "
        'themselves. Their clips are their own: `kind` "host", only them in `people`, '
        "the same `place` each time, and each shot's `action` says how they deliver that "
        "stretch (the face, the hands, the energy), never the words. Every other clip is "
        "B-roll cut in over their voice, without them in it. Put them on screen for the "
        "hook, each turn and the close: about 40 to 47% of the video, a few seconds at a "
        "time."
    ),
    "acts": (
        "{who} presents this video by acting in it: no clip shows them talking to camera. "
        "They are a person in the B-roll, named in `people` wherever the picture shows "
        "them doing what the narration says. Nobody's lips move."
    ),
}
FRAMING = "The action stays in the upper two-thirds of the frame, the bottom corners clear."


# A UGC presenter filmed on Omni says the lines themselves (omni_talker.PIECE, in the plan's
# own fields): the video is a Dialogue one with one speaker, and B-roll laid over their voice.
TALKER = ("{who} presents this video and says every spoken line of the script to camera, "
          "filling the frame, in clips of their own: a line with no speaker label is theirs "
          "too. Their lines in one place share one clip of up to {most} s, in script order, as "
          "few clips as the lines allow, each ending where one of the script's sentences ends. "
          "Size each clip to its words: about 2.6 words a second (2.1 for a slow, heavy line) "
          "plus about 1 s. Never a filler word to pad one.\n"
          "B-roll is cut in over their voice, never between their clips: a B-roll clip has "
          "`kind` \"broll\", comes right after the clip that says the line it shows, gives "
          "that line's number in each shot's `line` (the line is heard under it; nobody speaks "
          "in it) and leaves them out of `people`. They stay on screen for the hook, an "
          "opinion, anything said straight to the viewer and the close; B-roll is only for "
          "the phrases that gain from a picture, a few seconds each, under half the video in "
          "all.")  # fmt: skip  # Reed, 11 Nov: video 370's B-roll hid two thirds of him


def talker_block(who: str, most: int) -> str:
    """<talker> for the plan call of a presenter filmed on Omni (app/omni_talker.py)."""
    return f"<talker>\n{TALKER.format(who=who, most=most)}\n</talker>"


def host_block(who: str, how: str) -> str:
    """<host> for the plan call: who presents, and how they appear in this video."""
    return f"<host>\n{HOSTS[how].format(who=who[:1].upper() + who[1:])}\n</host>"


def motion(plan: dict | None) -> str:
    """The talker's motion note for their one take: how the plan's host clips say they
    deliver it (each `action`, once), as long as HeyGen's note may be; "" with none."""
    from app.talker import LONGEST_MOTION

    said = [s["action"].strip() for c in (plan or {}).get("clips") or [] if c.get("kind") == HOST
            for s in c["shots"] if s["action"].strip()]  # fmt: skip
    return " ".join(dict.fromkeys(said))[:LONGEST_MOTION]


def narrated_lines(script: str) -> list[tuple[int, str]]:
    """Each line a narrator (or a presenter talking to camera) says, with the number of the
    script line it comes from: `check.narration_text`'s lines, in order."""
    raw = [unnoted(x).strip() for x in script.splitlines()]
    out, at = [], 0
    for said in check.narration_text(script).splitlines():
        at = next((n for n in range(at, len(raw)) if raw[n].endswith(said)), at)
        out.append((at + 1, said))
        at += 1
    return out


def sentence_lines(script: str) -> list[int]:
    """The script line each sentence of a narration comes from, in the order the narration is
    timed (`narration.sentences`): a script line holding several sentences is named once for
    each."""
    return [n for n, said in narrated_lines(script) for _ in narration.sentences(said)]


def clock(script: str, timing: dict, narrated: bool) -> dict[int, tuple[float, float]]:
    """When each script line is heard in the take: {line number: (start, end)}, a line of
    several sentences from its first one's start to its last one's end. A song's timed lines
    are its sung ones, in order (`song_breakdown.guessed` counts them the same way)."""
    if narrated:
        numbers = sentence_lines(script)
    else:
        numbers = [n for n, x in enumerate(script.splitlines(), 1)
                   if not check.SECTION.match(x) and check.LIP_SYNC.sub("", x).strip()]  # fmt: skip
    out: dict[int, tuple[float, float]] = {}
    for n, x in zip(numbers, timing.get("lines") or [], strict=False):
        a, b = out.get(n, (x["start"], x["end"]))
        out[n] = (min(a, x["start"]), max(b, x["end"]))
    return out


def audio(db: Session, project: Project, script: str) -> dict | None:
    """The take a timed video is planned to, as the plan's check and its save read it: its id,
    its length, where the last shot ends (a narration's last picture may hold FINAL_HOLD past
    the last word), every measured start an `at` may land on (each line's and word's; a song's
    section edges, cuts and beats too) and each script line's time. None: no track in use (a
    Dialogue video, or a talker filmed on Omni)."""
    from app import director_song

    take = song_breakdown.take_for(db, project)
    if take is None or not take.timing or director_song.kind(db, project) is None:
        return None
    timing, narrated = take.timing, take.kind == narration.KIND
    parts = timing.get("sections") or []
    starts = {0.0, *(x["start"] for x in timing.get("lines") or []),
              *(w["start"] for w in timing.get("words") or []), *(timing.get("beats") or []),
              *(x["start"] for x in parts),
              *(c for x in parts for c in x.get("cuts") or [])}  # fmt: skip
    seconds = float(timing["seconds"])
    return {"take_id": take.id, "seconds": seconds, "narrated": narrated,
            "hold": narration.FINAL_HOLD if narrated else 0.0,
            "starts": sorted(round(s, 2) for s in starts if 0 <= s < seconds),
            "lines": {str(n): list(span)
                      for n, span in clock(script, timing, narrated).items()}}  # fmt: skip


def spans(plan: ShootingPlan, audio: dict) -> list[tuple[float, float]]:
    """Each shot's time in the track, in order: from its `at` to the next shot's, the last to
    the end of the track (and a narration's hold, when it's B-roll's to hold)."""
    shots = [(s, c) for c in plan.clips for s in c.shots]
    hold = audio["hold"] if shots and shots[-1][1].kind != HOST else 0.0
    ats = [s.at for s, _ in shots]
    return list(zip(ats, [*ats[1:], round(audio["seconds"] + hold, 2)], strict=True))


def snapped(plan: ShootingPlan, audio: dict, most: int) -> list[str]:
    """The plan put on the track, in place: every clip one kind (B-roll unless it's the
    talker's), no shot with a line of its own, the first shot at 0 and each `at` on the nearest
    measured start; then each clip the video model can't make in one go cut at a shot's edge
    (`packed`). What only the director can fix ([] if nothing): a shot that starts no later
    than the one before it, a B-roll shot under a second long (its clip's prompt times it in
    whole seconds), or one longer than the model's longest clip."""
    starts, first = audio["starts"], True
    for c in plan.clips:
        c.kind = HOST if c.kind == HOST and audio.get("talks") else BROLL
        for s in c.shots:
            s.line, s.how = None, ""
            s.at = 0.0 if first else min(starts, key=lambda t: abs(t - s.at))
            first = False
    plan.voices = []
    timed, fixes, clips = iter(spans(plan, audio)), [], []
    for c in plan.clips:
        mine = [next(timed) for _ in c.shots]
        for n, (a, b) in enumerate(mine, 1):
            if b <= a or (c.kind != HOST and b - a < SHORTEST):
                fixes.append(SHORT.format(c=c.id, n=n, at=a, end=b))
            elif c.kind != HOST and b - a > most:
                fixes.append(TOO_LONG.format(c=c.id, n=n, s=b - a, most=most))
        clips += packed(c, mine, most)
    if not fixes:
        plan.clips = clips
        for k, c in enumerate(clips, 1):
            c.id = f"c{k}"
    return fixes


def packed(clip: PlanClip, spans: list[tuple[float, float]], most: int) -> list[PlanClip]:
    """A B-roll clip as the video model can make it: past the model's longest clip, or past
    song_breakdown.PEOPLE_MAX with people in it (faces hold up only so long), it is cut where
    one of its shots starts into clips that fit, each keeping the clip's own words. The
    talker's clips are cut from their one take, at any length."""
    people = any(s.people for s in clip.shots)
    limit = min(most, song_breakdown.PEOPLE_MAX) if people else most
    if clip.kind == HOST or spans[-1][1] - spans[0][0] <= limit:
        return [clip]
    groups, start = [[]], spans[0][0]
    for s, (a, b) in zip(clip.shots, spans, strict=True):
        if groups[-1] and b - start > limit:
            groups, start = [*groups, []], a
        groups[-1].append(s)
    return [clip.model_copy(update={"shots": g}) for g in groups]


def song_part(plan: ShootingPlan, shot_ids: list[str], audio: dict) -> dict:
    """The plan's times as the song part a breakdown row keeps beside its shots
    (song_breakdown): each shot's start and end in the take, and `sung` for the talker's
    shots, who say that stretch to the lens."""
    kinds = [c.kind for c in plan.clips for _ in c.shots]
    shots = {sid: {"start": round(a, 2), "end": round(b, 2), "sung": kind == HOST}
             for sid, (a, b), kind
             in zip(shot_ids, spans(plan, audio), kinds, strict=True)}  # fmt: skip
    return {"take_id": audio["take_id"], "shots": shots}


def heard(audio: dict, a: float, b: float) -> list[int]:
    """The script lines heard between `a` and `b` of the track: half a second of each, or
    half the line (as check._line_clock judges a shot against its lines)."""
    return [int(n) for n, (s, e) in audio["lines"].items()
            if min(b, e) - max(a, s) >= min(0.5, (e - s) / 2)]  # fmt: skip


def follow_take(plan: dict, song: dict) -> dict:
    """The plan after the video moved to another take (song_breakdown.follow_take): each
    shot's `at` is its new start, so nothing is planned again. A plan whose shots aren't the
    song part's any more (an edit since) is kept as it is."""
    starts = sorted(t["start"] for t in song["shots"].values())
    if len(starts) != sum(len(c["shots"]) for c in plan["clips"]):
        return plan
    at = iter(starts)
    clips = [{**c, "shots": [{**s, "at": next(at)} for s in c["shots"]]} for c in plan["clips"]]
    return {**plan, "clips": clips}
