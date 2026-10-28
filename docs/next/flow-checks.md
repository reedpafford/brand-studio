# Flow checks (Flow-QA's living checklist)

Every flow in docs/next/flows.md, every state, and when it was last walked on the test site or in the browser tests (free stand-ins only, phone 390 and desktop).
Until flows.md lands, the song-ad rows below come from the approved spec (docs/research/starpop-2026-10-28/spec.md, feature 1). They're renamed to match flows.md when it does.

**Marks:** ✅ passes · ❌ fails (see Open failures) · ⬜ not built yet · — doesn't apply.
**States walked for every step:** empty · loading · queued · running · done · failed · refused · over budget / allowance · owner · editor · 390 · desktop · back / Undo · leaving the page mid-run · "Out of date" on later steps.
A state passes only if the person sees what's happening and has one press that moves them on (rule 22), and every paid press shows its price first (rule 24, spec feature 6).

## Song ads (feature 1)

| # | Flow | Steps | States | 390 | Desktop | Last checked |
|---|---|---|---|---|---|---|
| S1 | Owner starts a song script | New script → Song | ⬜ | ⬜ | ⬜ | — |
| S2 | Lyrics and style line | paste lyrics, or "Write 2 song directions" (paid) → pick one → lyrics lock | ⬜ | ⬜ | ⬜ | — |
| S3 | Make the song | "Make 2 takes" (paid) → play → Preferred → "Make 2 more" | ⬜ | ⬜ | ⬜ | — |
| S4 | Change the preferred take after the breakdown | Preferred → later steps "Out of date" | ⬜ | ⬜ | ⬜ | — |
| S5 | Cast read and Breakdown from the song | word timings → shots with time ranges → Sung / B-roll flip | ⬜ | ⬜ | ⬜ | — |
| S6 | Publish the song script | Publish → lines, cast, breakdown and song final (rule 31) | ⬜ | ⬜ | ⬜ | — |
| S7 | Editor makes the video | Assets → Breakdown (waveform) → Storyboard → Clips (Sung slices) | ⬜ | ⬜ | ⬜ | — |
| S8 | Final cut with the song under it | Downloads → stitched video plus song (free) | ⬜ | ⬜ | ⬜ | — |

## Effects on other steps (checked on every PR that touches a step)

| Change | Must mark "Out of date" | Must stay as is | Last checked |
|---|---|---|---|
| Lyrics edited (before publish) | song takes, breakdown, storyboard, clips | cast and looks | — |
| Preferred song take switched (per video, by the editor) | that video's breakdown time ranges, Sung slices, clips | the script, other videos, stills that don't depend on timing | — |
| A shot flipped Sung ↔ B-roll (per video) | that shot's clip prompt and price | other shots, the script, other videos | — |
| Style line edited | song takes | lyrics | — |

## Open failures
None open. The #737 screen plan passes on paper; the questions left are Next-Lead's, in flows.md.

Fixed in #737 at 8271b0fd, 6af52e4e (rule-31 ruling: per-video Preferred, takes and flips), 8068f911 (take-delete guard for videos) and 86dc2dd9 (no take fits the cap) (on paper; re-checked on the built screens): cap block, timing fallback, unsung line, Sung problems, refusal by style, restart, take-delete guard, trim and hold, 390 takes layout, "up to N" pricing. To re-check on the built screens.

## Walks
| Date | PR / commit | Flows | Result |
|---|---|---|---|
| 2026-10-28 | #737 (screen plan, docs) | S1–S8 on paper | FAIL: 7 open, see above |
| 2026-10-28 | #737 at 8271b0fd | S1–S8 on paper | 13/13 fixed; rule-31 alignment still open |
| 2026-10-28 | #737 at 6af52e4e | S1–S9 on paper | PASS on rule 31; 2 small open |
| 2026-10-28 | next at 4b89a38 (baseline, before Next work) | all existing browser tests, 390 and desktop, free stand-ins | PASS: 52 passed, 1 skipped (3.8 min) |
| 2026-10-28 | #737 at 97c4f14e | S1–S9 on paper | PASS |
