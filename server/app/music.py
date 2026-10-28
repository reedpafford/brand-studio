"""Song ads' music: one interface, whichever service sings the song.

Each service turns locked lyrics and a style line into a job for the worker. MiniMax Music
(on Replicate) is the one we use: it takes the lyrics as their own field and its auto-lyrics
switch stays off, so the words are sung as written (rules 19 and 31). Suno has no official
API yet, so its slot stays off until Reed has real access. Each take is one job and one song
file; a request makes two (Starpop's habit), one marked Preferred."""

import re
from dataclasses import dataclass

TAKES = 2  # songs per "Make 2 takes" press
MAX_STYLE = 2000  # MiniMax's prompt limit (characters)
MAX_LYRICS = 3500
# The section tags MiniMax knows. Any other [tag] line would be sung as words, so it is
# dropped (and said); numbered tags ("[Verse 2]") become the plain tag.
TAGS = {
    t.lower(): t
    for t in ("Intro", "Verse", "Pre Chorus", "Chorus", "Post Chorus", "Hook", "Bridge",
              "Interlude", "Transition", "Break", "Build Up", "Inst", "Solo", "Outro")
}  # fmt: skip
TAG = re.compile(r"^\s*\[([^\]]*)\]\s*$")

NO_LYRICS = "Add the lyrics first (or pick a song direction): the song sings them word for word."
TOO_LONG = "The lyrics are too long for one song (3,500 characters at most). Cut a verse."
STYLE_TOO_LONG = "The style line is too long (2,000 characters at most). Shorten it."
SUNO_OFF = "Suno isn't connected yet. MiniMax Music makes the song for now."
# What a failed take, or its timing, says (rule 22: the reason, nothing charged, Try again).
FAILED = "The song couldn't be made this time. Nothing was charged; press Try again."
REFUSED = (
    "The music service wouldn't sing these lyrics: it read some words as unsafe. Change those "
    "words, then press Try again. Nothing was charged."
)
COPYRIGHT = (
    "The music service wouldn't use this style line: it may name a real artist or song "
    "(“{}”). Describe the sound instead (genre, voice, tempo, mood), then press Try again. "
    "Nothing was charged."
)
# Timing is free. A slow or interrupted read may work next time; a file that can't be read
# fails the same way every time, so that one points to the other take instead.
TIMING_FAILED = "We couldn't read this song's timing. It's free to try again."
TIMING_UNREADABLE = (
    "This take's file can't be read, so its timing can't be measured. Use the other take or "
    "make 2 more."
)


class NotReady(ValueError):
    """The request can't be made as it is; the message says what to do."""


@dataclass(frozen=True)
class Lyrics:
    text: str  # what is sent: tags cleaned, every word as written
    dropped: list[str]  # tags we removed, for a plain note


def clean(lyrics: str) -> Lyrics:
    """Lyrics as the music service gets them. Only tag lines change; words never do."""
    lines, dropped = [], []
    for line in lyrics.strip().splitlines():
        tag = TAG.match(line)
        if not tag:
            lines.append(line.rstrip())
            continue
        name = re.sub(r"[\s\-]*\d+$", "", tag.group(1)).replace("-", " ").strip().lower()
        if name in TAGS:
            lines.append(f"[{TAGS[name]}]")
        else:
            dropped.append(line.strip())
    return Lyrics("\n".join(lines).strip(), dropped)


@dataclass(frozen=True)
class MusicService:
    id: str  # the catalogue model, or the slot's own name
    name: str
    provider: str  # which worker provider runs it
    on: bool
    off_reason: str = ""

    def job(self, lyrics: str, style_line: str) -> dict:
        """The worker input for one take. Raises NotReady with a plain reason."""
        if not self.on:
            raise NotReady(self.off_reason)
        words = clean(lyrics)
        if not words.text or all(TAG.match(ln) for ln in words.text.splitlines()):
            raise NotReady(NO_LYRICS)
        if len(words.text) > MAX_LYRICS:
            raise NotReady(TOO_LONG)
        if len(style_line) > MAX_STYLE:
            raise NotReady(STYLE_TOO_LONG)
        return {
            "model": self.id,
            "input": {
                "lyrics": words.text,
                "prompt": style_line.strip(),
                "lyrics_optimizer": False,  # never writes its own words
                "is_instrumental": False,
                "audio_format": "mp3",
            },
        }


SERVICES = {
    s.id: s
    for s in (
        MusicService("minimax-music-2.6", "MiniMax Music", "replicate", on=True),
        MusicService("suno", "Suno", "suno", on=False, off_reason=SUNO_OFF),
    )
}
DEFAULT = "minimax-music-2.6"


def failure(detail: str, style_line: str = "") -> str:
    """A failed take's plain reason, from the service's raw error (kept owner-only): the
    style line to change, the lyrics to change, or just Try again."""
    if re.search(r"copyright|artist|trademark|infring", detail, re.I):
        return COPYRIGHT.format(style_line.strip())
    if re.search(r"sensitive|moderat|safety|unsafe|flagged|violat", detail, re.I):
        return REFUSED
    return FAILED
