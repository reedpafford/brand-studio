# Winner breakdowns

One JSON file per reel in the Instagram Reference Library (`../instagram-library-index.csv`), plus winners the
owner added on the server that have only a server Gemini watch (their `evidence` field says so). Each file is a
concrete, timestamped breakdown that `winner_examples.py` hands to the script writer, the shot planner and the
Seedance prompt writer as "feel like these" examples (the 2–3 closest to the brief). Copy and match modes skip
them: there the project's own reference is the example.

## Fields

| Field | What it is |
|---|---|
| `style` | `3d`, `mixed` or `live`. Only `3d` and `mixed` reels are used as examples. |
| `logline`, `tags` | One-sentence story and retrieval tags (doubter, setting, hustle, story shape, tone). |
| `pacing_profile` | fast / medium / slow. |
| `stats` | Measured on the stylized 3D shots only: shot count, median and longest shot, shots under 1 s, spoken lines, words per second while speaking, share of runtime with speech. |
| `live_shots` | Shots that are live-action / real footage (outros, real clips). They are left out of the stats and of every description. |
| `cut_times` | Every detected cut, in seconds. |
| `hook` | First seconds: the mechanic and the first line. |
| `moment` | The single moment that lands hardest, and why. |
| `beats` | 5–12 beats with start/end, what happens, the emotion on screen, the camera and the cut rhythm. |
| `lines` | Every spoken line with its time, speaker and delivery (volume, pace, pitch, emotion). |
| `voice_arc`, `camera_language`, `why_it_works` | Short summaries. |
| `gemini_watch` | From the server's Gemini watch of the same reel (with sound): hook, turn, payoff, why it works, timestamped camera notes, montages. On-screen text and music notes are dropped. |

Captions, text overlays and music are added by the editors in post, so the breakdowns never describe them.
nateassets and cevrico are the gold-standard accounts: retrieval gives them the edge in any close call.

## How they were made (local, no paid calls)

`tools/winner_breakdowns/extract.py` measures each reel: ffmpeg scene-change cuts, one keyframe per shot tiled
into contact sheets, a local Whisper (`small`) transcript with timings, and per-line loudness (mean/peak dB),
speech rate and the pause before each line. `tools/winner_breakdowns/breakdown.py` gives that evidence and the
contact sheets to local Codex, which writes the structured breakdown. Delivery notes come from the measured
loudness, rate and pauses plus the faces in the frames; they are an informed reading, not a verified audio
analysis. Cut detection can count a hard caption change or a flash as a cut, so treat shot counts as close, not
exact.

Re-run for new reels:

```bash
python3 -I tools/winner_breakdowns/extract.py <reel.mp4> <scratch>/reels/<id>
python3 -I tools/winner_breakdowns/breakdown.py <scratch> <id> docs/winners/breakdowns/<id>.json <account> <views> <url>
```

The server's Gemini watches are layered on from a read-only export (the export itself never goes in the repo):

```bash
python3 tools/winner_breakdowns/merge_gemini.py <live-export.json.gz>
```
