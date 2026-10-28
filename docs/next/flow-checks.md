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
| S2 | Lyrics and style (word count, cap, end-line Advice) | ⬜ | API: ✅ empty style, no lyrics → 422 | #748 at 9a44a675 (API) |
| S3 | Write 2 song directions | ⬜ | ⬜ | — |
| S4 | Make the song: takes, Preferred, timing | ⬜ | API: ❌ 3 states (see Open failures) | #748 at 9a44a675 (API, no screen yet) |
| S5 | Cast: who sings | ⬜ | ⬜ | — |
| S6 | Breakdown preview (owner) | ⬜ | ⬜ | — |
| S7 | Publish | ⬜ | API: ✅ takes read-only once published | #748 at 9a44a675 (API) |
| V2a | The video's own song (editor: Change song, Make 2 more; rule 31) | ⬜ | API: ✅ 5 states, ❌ over-cap take | #750 at b4ef028e (API) |
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
| S4 U | Deleting the Preferred take succeeds and hands the mark on; if the other sings older words, nothing is Preferred | 409 "Make another take Preferred first" | #748 at 9a44a675 |
| S4 | Too long (after): an 800 s take comes back ready and Preferred | Can't be Preferred, with the reason; **Use the first N:NN** | #748 at 9a44a675 |
| S7 | A song script with no take can be published; its videos get no song and no way to get one | 409 "Make the song first" | #750 at b4ef028e |
| V2a | An over-cap take can become the video's song | 409 "Too long for this video" + **Use the first N:NN** | #750 at b4ef028e |
| S4 | Suno: one request = 2 songs at a 1-credit placeholder; limits 5,000 / 1,000. screens.md (#742) still has 3,500 / 2,000 and "3 for 2, 2 for one" | screens.md follows flows.md S4 | #746 at 6efea144 |
| S4 | flows.md's Suno recipe adds about 110 characters to the style line; with a 1,000 limit the person's line must stop at about 890 | Limit on screen leaves room; out of date compares the person's own line | #740 at 823c0bd0 vs #746 |
| VS1, LW1 | The "finished video" warning covers only breakdown, look and flavour changes, not song, style, model or shape switches | Same line in every confirm that dates a finished video | #743 at ba9010cf |
| Publish | Flavour at Publish has no edge states (no flavours, one, none picked, a product added later) | Words and a press for each | #743 at ba9010cf |
| Final cut | Making a cut while some clips are out of date is undefined | Allow with a warning, or block with **Update everything after this** | #743 at ba9010cf |
| ST1 | Zack D and Skeleton are `format` in #753 but looks in flows.md Q4, so two of Reed's first four styles can't be picked | Settle with Reed's answer to Q4 | #753 at 49b73764 |
| S4 B (rule 4) | The decline past the week says "N free credits" (credits.over_allowance, also on main) | Drop "free" | #748 at 9a44a675 |

Paper reviews passed: screen plan (#737, #742), flows.md song ads (#740 at e7fad772), flows.md items 2–6 (#743 at 05ef4860). Every state there is to be re-checked on the built screens.

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
| 2026-10-28 | #740 at 91f4b387 | S1–S7, V1–V6, V2a on paper | Rule 31 PASS; 3 dead ends still open, plus 1 new |
| 2026-10-28 | #745 at 773c1de (style registry, prompts only) | House prompts unchanged; server tests | PASS: 15/15 renders identical, 691 tests pass |
| 2026-10-28 | #740 at e7fad772 | S1–S7, V1–V6, V2a on paper | PASS |
| 2026-10-28 | #743 at 05ef4860 | ST, BR, VS, OR, layout on paper | PASS (one wording note on the VS1 confirm) |
| 2026-10-28 | #746 at 8d85af53 (music stand-in, timing) | every `fake:` marker through make → time → message | FAIL: false "sung twice" on a repeated chorus |
| 2026-10-28 | #748 at 9a44a675 (song-take routes) | S2, S4, S7 through the API: 8 walk cases on the stand-ins | FAIL: delete guard, sung twice, too long (after); 5 states pass |
| 2026-10-28 | #750 at b4ef028e (V2a routes) | V2a, S7 through the API | FAIL: publish with no take, over-cap take; 5 states pass |
| 2026-10-28 | #748 at 9a44a675 | full server suite | PASS |
| 2026-10-28 | #746 at 6efea144 (Suno) | times_sung, TooLong, quote length | PASS (Advice note: a repeat names both chorus copies) |
| 2026-10-28 | #743 at ba9010cf (UX audit names and moves) | Out of date viewable, finished video, flavour, shape | PASS with 3 gaps |
| 2026-10-28 | #753 at 49b73764 (the rest of the styles) | House prompts, style switches | PASS: 15/15 House renders identical, 18 tests; 1 mismatch with flows.md Q4 |
