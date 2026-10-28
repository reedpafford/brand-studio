"""Song ads' music: one interface, whichever service sings the song. Suno is the one we use
(Reed, 2026-10-28: "the exact software we would use live").

Suno has no public API yet (a partner programme opened in July 2026; platform.suno.com has no
public docs or pricing), and no unofficial wrapper is used. So no real Suno provider is
registered: songs say "Songs aren't switched on here" until Reed has access and the adapter
is written to Suno's docs. The free stand-in (BS_FAKE_PROVIDERS) mirrors what Suno's app
does. Assumptions, to check against those docs:
- A1 "Custom" generation: our lyrics, sung exactly as written, plus a style line; never
  instrumental and never Suno's own words (rules 19 and 31).
- A2 One request returns 2 songs (as in Suno's app), so "Make 2 takes" is one job.
- A3 The songs come back as audio file links; we read the timing ourselves (free), so nothing
  depends on Suno's own timings.
- A4 Price: unknown. Estimated at 1 credit a request until Suno gives a real one (rule 2)."""

import re

PROVIDER = "suno"
TAKES = 2  # songs per request (A2)
# Suno's Custom mode limits, as its app shows them (Starpop study, 2026-10-28)
MAX_STYLE = 1000
MAX_LYRICS = 5000
TAG = re.compile(r"^\s*\[([^\]]*)\]\s*$")  # [Verse 1], [Chorus]: directions, never sung

NO_LYRICS = "Add the lyrics first (or pick a song direction): the song sings them word for word."
TOO_LONG = "The lyrics are too long for one song (5,000 characters at most). Cut a verse."
STYLE_TOO_LONG = "The style line is too long (1,000 characters at most). Shorten it."
# What a failed request, or a take's timing, says (rule 22: the reason, nothing charged,
# Try again).
FAILED = "The songs couldn't be made this time. Nothing was charged; press Try again."
REFUSED = (
    "The music service wouldn't sing these lyrics: it read some words as unsafe. Change those "
    "words, then press Try again. Nothing was charged."
)
QUOTED = 80  # characters of the style line a message repeats
COPYRIGHT = (
    "The music service wouldn't use this style line: it may name a real artist or song "
    "(“{}”). Describe the sound instead (genre, voice, tempo, mood), then press Try again. "
    "Nothing was charged."
)
# Timing is free. A slow or interrupted read may work next time; a file that can't be read
# fails the same way every time, so that one points to the other take instead.
TIMING_FAILED = "We couldn't read this song's timing. It's free to try again."
TIMING_TOO_LONG = (
    "This take is over 15 minutes, far longer than an ad, so its timing isn't measured. Use "
    "the other take, or shorten the lyrics and make 2 more."
)
TIMING_UNREADABLE = (
    "This take's file can't be read, so its timing can't be measured. Use the other take or "
    "make 2 more."
)


class NotReady(ValueError):
    """The request can't be made as it is; the message says what to do."""


def sung(lyrics: str) -> list[str]:
    """The lyric lines that are sung: everything but [tag] lines and blank lines."""
    return [ln.strip() for ln in lyrics.splitlines() if ln.strip() and not TAG.match(ln)]


def job(lyrics: str, style_line: str) -> dict:
    """The worker input for one request (2 takes). Raises NotReady with a plain reason."""
    lyrics = lyrics.strip()
    if not sung(lyrics):
        raise NotReady(NO_LYRICS)
    if len(lyrics) > MAX_LYRICS:
        raise NotReady(TOO_LONG)
    if len(style_line) > MAX_STYLE:
        raise NotReady(STYLE_TOO_LONG)
    # A1: Custom mode, our words only.
    return {"input": {"lyrics": lyrics, "style": style_line.strip(), "instrumental": False}}


def failure(detail: str, style_line: str = "") -> str:
    """A failed request's plain reason, from the service's raw error (kept owner-only): the
    style line to change, the lyrics to change, or just Try again."""
    if re.search(r"copyright|artist|trademark|infring", detail, re.I):
        quoted = style_line.strip()
        quoted = quoted if len(quoted) <= QUOTED else quoted[:QUOTED].rsplit(" ", 1)[0] + "…"
        return COPYRIGHT.format(quoted)
    if re.search(r"sensitive|moderat|safety|unsafe|flagged|violat", detail, re.I):
        return REFUSED
    return FAILED
