"""One starting frame for a talker in one spot (Reed, 9 Nov: "the best fix for that request would
be using the same starting frame - as long as the hands are in like a neutral position"). Video
315: a man filming himself in his parked car was made in 5 Omni pieces, each from its own still,
so every piece showed another car, lot, lens and angle, though the plan said "same car, same
light". Now the pieces of one person talking to camera in one place all open on ONE still: the
first piece's, drawn once with them at rest (`NEUTRAL`), given as [Image1] to every one of them,
remakes and revisions included. Automatic in the UGC style; any style when a note or the brief
asks for one spot (`ONE_SPOT`). The plan may give a piece its own opening picture (`own_frame`,
saying why: an insert of the phone screen, B-roll), and a piece whose first shot shows a screen
keeps its own; a one-spot note overrides both. A narrated video's talker is HeyGen's, already
one still for the whole narration (app/talker.py)."""

import re

from sqlalchemy.orm import Session

from app.models.projects import Project

NEUTRAL = (
    " This one still opens every piece of them talking here, so catch them at rest, before "
    "anything happens: looking straight into the lens, mouth closed, a relaxed face, hands "
    "relaxed and low and empty (filming themselves: the phone held steady at arm's length)."
)
ONE_SPOT = re.compile(
    r"\b(?:one|same|single)\s+(?:spot|place|position|location|angle|set-?up)\b"
    r"|\b(?:stationary|static|fixed|locked[- ]off)\s+camera\b"
    r"|\bcamera\s+(?:stays?|still|fixed|locked|in\s+one)\b"
    r"|\bsame\s+(?:start(?:ing)?|first|opening)\s+(?:frame|still|shot)\b",
    re.I,
)


def one_spot(project: Project) -> bool:
    """The brief or a note in the video's chat asks for the camera in one spot."""
    said = [project.goal or "", *((m.get("text") or "") for m in project.director_chat or [])]
    return any(ONE_SPOT.search(t) for t in said)


def _talker(shots: list[dict]) -> str | None:
    """The one person a piece shows, when they say a line in it."""
    people = {c for s in shots for c in s.get("character_ids") or []}
    return people.pop() if len(people) == 1 and any(s.get("line") for s in shots) else None


def followers(data: dict | None, ugc: bool, forced: bool) -> dict[str, str]:
    """Each piece that opens on another's still -> that piece: the first piece of the same
    talker in the same place (any place, `forced`)."""
    if not data or not (ugc or forced):
        return {}
    shots = {s["id"]: (s, sc) for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    first: dict[tuple[str, str], str] = {}
    out: dict[str, str] = {}
    for clip in data.get("clips", []):
        mine = [shots[i] for i in clip.get("shot_ids", []) if i in shots]
        who = _talker([s for s, _ in mine])
        if not who or (not forced and (clip.get("own_frame") or mine[0][0].get("screen_ids"))):
            continue
        opens, scene = mine[0]
        place = opens.get("place_id") or re.sub(r"\W+", " ", scene.get("heading", "")).lower()
        key = (who, "" if forced else place.strip())
        if key in first:
            out[clip["id"]] = first[key]
        else:
            first[key] = clip["id"]
    return out


def shared(db: Session, project: Project | None, data: dict | None = None) -> dict[str, str]:
    """The video's followers on its newest plan (or `data`): a story video only."""
    from app import looks, narration, talker
    from app.clip_prompts import newest

    if project is None or narration.video_kind(db, project) != "story":
        return {}
    if data is None:
        data = (row.data if (row := newest(db, project)) else None) if project.id else None
    ugc = looks.base(project.look or looks.DEFAULT) in talker.LOOKS
    return followers(data, ugc, one_spot(project))


def opening(data: dict, clip_id: str) -> str | None:
    """The shot a piece opens on (its still's)."""
    return next((c["shot_ids"][0] for c in data.get("clips", []) if c["id"] == clip_id), None)
