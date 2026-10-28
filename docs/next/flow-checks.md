# Flow checks (Flow-QA's living checklist)

Every flow in docs/next/flows.md, every state, and when it was last walked on the test site or in the browser tests (free stand-ins only, phone 390 and desktop).
Flow ids follow docs/next/flows.md (#740 song ads, #743 items 2–6). The screen plan (docs/next/screens.md) numbers the same song steps S1–S9 a little differently; flows.md wins.

**Marks:** ✅ passes · ❌ fails (see Open failures) · ⬜ not built yet · — doesn't apply.
**States walked for every step:** empty · loading · queued · running · done · failed · refused · over budget / allowance · owner · editor · 390 · desktop · back / Undo · leaving the page mid-run · "Out of date" on later steps.
A state passes only if the person sees what's happening and has one press that moves them on (rule 22), and every paid press shows its price first (rule 24, spec feature 6).

## Song ads (flows.md item 1)

| Id | Flow | 390 | Desktop | Last checked |
|---|---|---|---|---|
| S1 | New script: Song | ⬜ | ⬜ | — |
| S2 | Lyrics and style (word count, cap, end-line Advice) | ⬜ | ⬜ | — |
| S3 | Write 2 song directions | ⬜ | ⬜ | — |
| S4 | Make the song: takes, Preferred, timing | ⬜ | ⬜ | — |
| S5 | Cast: who sings | ⬜ | ⬜ | — |
| S6 | Breakdown preview (owner) | ⬜ | ⬜ | — |
| S7 | Publish | ⬜ | ⬜ | — |
| — | The video's own song (editor: Change song, Make 2 more; rule 31) | ⬜ | ⬜ | — |
| V1 | Make this version | ⬜ | ⬜ | — |
| V2 | Breakdown on the song (Sung / B-roll, split, join) | ⬜ | ⬜ | — |
| V3–V4 | Assets, Storyboard (Sung stills as reference) | ⬜ | ⬜ | — |
| V5 | Clips: Sung and B-roll | ⬜ | ⬜ | — |
| V6 | Downloads: the song underneath | ⬜ | ⬜ | — |

Stand-in outcomes to walk (style-line markers, Next-Server PR 1): `fake:fail`, `fake:refuse`, `fake:copyright`, `fake:drop-line`, `fake:repeat-line`, `fake:long=N` (N past the cap, e.g. 800).

## Items 2–6 (flows.md #743)

| Id | Flow | 390 | Desktop | Last checked |
|---|---|---|---|---|
| ST1–ST3 | Style picker, downstream effects, switching a style on | ⬜ | ⬜ | — |
| BR1–BR2 | Brand page, import from website | ⬜ | ⬜ | — |
| VS1 | Video settings | ⬜ | ⬜ | — |
| OR1–OR4 | Projects, Media, Preferred and versions, cost log | ⬜ | ⬜ | — |
| Layout | Three columns, cost bar | ⬜ | ⬜ | — |

## Effects on other steps (checked on every PR that touches a step)

| Change | Must mark "Out of date" | Must stay as is | Last checked |
|---|---|---|---|
| Lyrics edited (before publish) | song takes, breakdown, storyboard, clips | cast and looks | — |
| Preferred song take switched (per video, by the editor) | that video's breakdown time ranges, Sung slices, clips | the script, other videos, stills that don't depend on timing | — |
| A shot flipped Sung ↔ B-roll (per video) | that shot's clip prompt and price | other shots, the script, other videos | — |
| Style line edited | song takes | lyrics | — |

## Open failures
| Where | State that fails | Fix expected | Found in |
|---|---|---|---|

| flows.md S4 / data.md | Rule 31 as merged (#739): Preferred take and new takes per video, but flows.md fixes them at publish and has no editor song step | An editor song step (#737 S3e); `projects.song_take_id`, `song_takes.project_id` | #740 |
| flows.md S4 | Timing failed offers only Try again (repeats) | **Make the other one preferred** / **Make 2 more** | #740 |
| flows.md S5 → V2 | "Nobody on camera", then a flip to Sung, has no singer | "Who sings this shot?" picker, free, Undo | #740 |
| flows.md S4 | Deleting the Preferred take when the other sings older words; deleting a take a video uses | Guard both, with the reason | #740 |
| flows.md vs #737/#742 | Step names, empty style (Advice vs block), the press for an unsafe refusal, sung-twice, Preferred while timing runs | Pick one in flows.md; the screens follow | #740 |
| ST2 | Per-style sheet on a library character (rule 12); editor dead end. Producer ruled: per-video look for editors, library sheet owner only | flows.md to write it in | #743 |
| ST1 | Publishing on an Off style | **Switch to House** at Publish | #743 |
| VS1 | A non-audio video model on a song video leaves Sung clips unmakeable | Grey them out, or Sung → B-roll with Undo | #743 |
| ST3 | Sample needs the brand's hero; no default cast yet | Stock character, or a picker | #743 |

The #737 screen plan passes on paper.

Fixed in #737 at 8271b0fd, 6af52e4e (rule-31 ruling: per-video Preferred, takes and flips), 8068f911 (take-delete guard for videos) and 86dc2dd9 (no take fits the cap) (on paper; re-checked on the built screens): cap block, timing fallback, unsung line, Sung problems, refusal by style, restart, take-delete guard, trim and hold, 390 takes layout, "up to N" pricing. To re-check on the built screens.

## Walks
| Date | PR / commit | Flows | Result |
|---|---|---|---|
| 2026-10-28 | #737 (screen plan, docs) | S1–S8 on paper | FAIL: 7 open, see above |
| 2026-10-28 | #737 at 8271b0fd | S1–S8 on paper | 13/13 fixed; rule-31 alignment still open |
| 2026-10-28 | #737 at 6af52e4e | S1–S9 on paper | PASS on rule 31; 2 small open |
| 2026-10-28 | next at 4b89a38 (baseline, before Next work) | all existing browser tests, 390 and desktop, free stand-ins | PASS: 52 passed, 1 skipped (3.8 min) |
| 2026-10-28 | #737 at 97c4f14e | S1–S9 on paper | PASS |
| 2026-10-28 | #742 at 972a31fd (song fields) | S2, S3 on paper | FAIL: 2 open |
| 2026-10-28 | #740 at 78300b55 (flows.md, song ads) | S1–S7, V1–V6 on paper | FAIL: rule 31, 3 dead ends, 4 disagreements |
| 2026-10-28 | #743 at 395c6005 (flows.md, items 2–6) | ST, BR, VS, OR, layout on paper | FAIL: 4 blocking, 4 smaller |
| 2026-10-28 | #742 at 4f9fbdf4 | S2, S3 on paper | PASS |
