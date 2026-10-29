# Flow checks (Flow-QA's living checklist)

Every flow in docs/next/flows.md, every state, and when it was last walked on the test site or in the browser tests (free stand-ins only, phone 390 and desktop).
Flow ids follow docs/next/flows.md (#740 song ads, #743 items 2–6). The screen plan (docs/next/screens.md) numbers the same song steps S1–S9 a little differently; flows.md wins.

**Marks:** ✅ passes · ❌ fails (see Open failures) · ⬜ not built yet · — doesn't apply.
**States walked for every step:** empty · loading · queued · running · done · failed · refused · over budget / allowance · owner · editor · 390 · desktop · back / Undo · leaving the page mid-run · "Out of date" on later steps.
A state passes only if the person sees what's happening and has one press that moves them on (rule 22), and every paid press shows its price first (rule 24, spec feature 6).

## Song ads (flows.md item 1)

| Id | Flow | 390 | Desktop | Last checked |
|---|---|---|---|---|
| S1 | New script: Song | ✅ | ✅ | #759 at 5698de50 |
| S2 | Lyrics and style (word count, cap, end-line Advice) | ✅ save, edit-with-takes confirm | ✅ | #759 at 5698de50 (word count, cap and end-line Advice not built) |
| S3 | Write 2 song directions | ⬜ | ⬜ | — |
| S4 | Make the song: takes, Preferred, timing | ✅ (too long not built) | ✅ (too long not built) | #759 at 19bbca56 (UI); #748 at 317efac0 (API) |
| S5 | Cast: who sings | ✅ (Nobody only on the stand-in) | ✅ | #775 at f424baa8 (Singer role from the cast read, pre-pick and out-of-date preview still to walk) |
| S6 | Breakdown preview (owner) | ⬜ | ⬜ | — |
| S7 | Publish | ✅ card: song, style, singer | ✅ | #775 at f424baa8 (UI); #750 (API guard) |
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
| S4 | flows.md's Suno recipe adds about 110 characters to the style line; with a 1,000 limit the person's line must stop at about 890 | Limit on screen leaves room; out of date compares the person's own line | #740 at 823c0bd0 vs #746 |
| Script header (390, on next already) | The title button "Rename …" is 32px tall | 44px | #759 walk |
| V2 (to walk) | `song_breakdown(written=False)` by default now; walk the editor's flip/split/join route when it lands | — | #755 at 691a5eb5 |
| Repo | `web/node_modules` committed as a symlink to a local path (`node_modules/` in .gitignore misses symlinks) | `git rm --cached`; ignore `node_modules` | #771 at 1b48be60, #773 at b3afd16f |
| Clips, Storyboard "Change this…" (live today) | "Changing…" can spin for good when the change has no job id or its job is never picked up: no timer, no Stop (audit G8, Blocker) | A timer, then "didn't finish" + Try again | #774 audit |
| Brand, Cast & places (live today) | Editors can edit the brand and Reed's characters; flows.md BR1 says owner edits, editors read; a sheet redo by an editor changes every video (rule 12) | Owner-only writes (audit N11, Next-Lead to agree) | #774 audit |
| Scripts, empty brand (live today) | An editor on an empty brand gets "The owner publishes scripts here…" with no press | A press beside it (audit S31/S23) | #774 audit |
| S4 (rule 3) | Trim → Preferred → Undo the trim leaves an over-cap take Preferred, and the script publishes (200) over the 729 cap | Un-trim hands Preferred back or refuses; `preferred()` and `use_in_video` skip over-cap takes | #748 at 3607b3d |
| S4 U (UI) | When the trim also makes the take Preferred, its Undo toast is replaced by "Take 1 is Preferred." (no Undo); the trim can't be undone | One toast, one Undo reversing both | #759 at da86aa07 |
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
| 2026-10-28 | #753 at 49b73764 (the rest of the styles) | House prompts, style switches | PASS: 15/15 House renders identical, 18 tests (Zack D / Skeleton as formats match flows.md ST1 "Voiceover-led entry") |
| 2026-10-28 | #743 at d16aef16 | Finished-video warning, cut with out-of-date clips, flavour edge states, Suno S4 | PASS |
| 2026-10-28 | #755 at 3a72323e (song prompts) | Song directions, song breakdown, Sung clips; House prompts | PASS on the prompts, 19 tests; FAIL on 2 effects (story clip prompts, editor-flip Advice) |
| 2026-10-28 | #743 at c8c5305d | ST1 voiceover-led entries, S3 unchecked claims | PASS |
| 2026-10-28 | #759 at 5698de50 (song screens S1, S2, S4) | Playwright at 1440 and 390: failed, refused, Advice, leave and return, delete guard, delete + Undo, lyrics-edit confirm, sideways scroll; plus the PR's song.e2e | FAIL: Next after the lyrics change, refused has no way on; 7 states pass |
| 2026-10-28 | #748 at 317efac0 (Suno) | 8 API walk cases | 6 pass (delete guard fixed); too long (after) still open |
| 2026-10-28 | #742 at c1f7ec80, #759 at 51f0e518 | Suno limits and per-request price | PASS; #759's two walk findings still open |
| 2026-10-28 | #759 at 19bbca56 | Playwright at 1440 and 390, 6 walk cases + song.e2e | PASS |
| 2026-10-28 | #750 at cb1c556d | V2a, S7 through the API | FAIL: same 2 (publish with no take, over-cap take) |
| 2026-10-28 | #759 at ba7852eb | Playwright at 1440 and 390 (refused → boxes open) | PASS, 12/12 |
| 2026-10-29 | #748 at 3607b3d, #750 at 0ae5902 | 13 API walk cases (cap + trim + Undo, publish guard, video song) | FAIL on 1: section `[Lip-sync]` dates takes; the rest pass |
| 2026-10-29 | #766 at bf5fbe3f (Clips words, Next-Layout) | Full browser suite at 390 and 1440; grey-button reasons, status chip, failure line, 44px on phones | PASS (52 passed, 1 skipped) |
| 2026-10-29 | #755 at 7164efc3 | Story clip prompts vs next; Sung Advice on editor flips; 28 tests | PASS (Zack D / Skeleton kind to settle) |
| 2026-10-29 | #759 at 99dc54a8 | Playwright at 1440 and 390: over the cap + trim, style refusal + default style, words refusal + Edit lyrics, earlier cases | PASS, 16/16 (note: the trimmed take could become Preferred itself) |
| 2026-10-29 | #771 at 1b48be60 (Storyboard words, Next-Layout) | Full browser suite at 390 and 1440; reasons, one amber, in-app confirm | Flow PASS (52 passed); FAIL on the committed node_modules symlink |
| 2026-10-29 | #759 at da86aa07, #748 at 3607b3d | Trim → auto-Preferred → Undo (Playwright 390/1440 + API) | FAIL: Undo lost (UI); untrim + publish breaks the cap (API) |
| 2026-10-29 | #755 at 691a5eb5 | `written=False` default, `narrated: yes` | PASS, 28 tests |
| 2026-10-29 | #773 at b3afd16f (Breakdown words, Assets loading, owner's OK) | Full browser suite at 390 and 1440 | Flow PASS (52 passed); FAIL on the committed node_modules symlink |
| 2026-10-29 | #774 (audit Part 6, docs) | Read for dead ends and rule breaks | 3 live items added to Open failures |
| 2026-10-29 | #775 at f424baa8 (S5 Singer, S7 Publish card, V1 song) | Playwright at 1440 and 390 + song.e2e | PASS (notes: Singer role from the cast read, out-of-date preview on a Singer change) |
| 2026-10-29 | #748 at 5c3d02f | `[Lip-sync]` section and line marks; untrim cap case | Lip-sync PASS; cap bypass through the trim's Undo still open |
