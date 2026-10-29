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
| V2a | The video's own song (editor: Change song, Make 2 more; rule 31) | ✅ | ✅ | #781 at 2a3751ca (UI; Delete hidden on the video's auto-Preferred own take until #783 merges); #783 at 9bf8afb (API) |
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
| Clips, Storyboard "Change this…" (live today) | "Changing…" can spin for good when the change has no job id or its job is never picked up: no timer, no Stop (audit G8, Blocker) | A timer, then "didn't finish" + Try again | #774 audit |
| Brand, Cast & places (live today) | Editors can edit the brand and Reed's characters; flows.md BR1 says owner edits, editors read; a sheet redo by an editor changes every video (rule 12) | Owner-only writes (audit N11, Next-Lead to agree) | #774 audit |
| Scripts, empty brand (live today) | An editor on an empty brand gets "The owner publishes scripts here…" with no press | A press beside it (audit S31/S23) | #774 audit |
| VS1 Shape | flows.md: a shape change puts stills and clips out of date with the redo price. Server: nothing is marked, stills keep the old shape, free; a video can mix shapes silently | Decided (Next-Lead): flows.md stands. Waiting on Next-Server: mark stills and clips out of date on a shape change, price the redo, Undo. #778's honest dialog is the interim | #778 at ef73d126 |
| S2 | Style limit 893: server message plain (#783 f8a3199a); screens updated to 893 on #759 16b9f166 | Re-walk | #759 |
| Usage (live today, small) | With 25+ brands the list pages at 25 + Show more; with "Show archived" ticked, a just-archived brand can sit behind Show more (reachable, not a dead end) | Archived first when shown | 10+ brands check |
| Song breakdown edit (#799, API only, not blocking) | After a reorder through the API, putting the plan back is not exact (1.1 0–12.58; 1.2–1.4 at 0.39 s). No screen reorders shots | Skip times from a row whose order differs, if a reorder ever reaches a screen | #799 at 8e20e1fa |
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
| 2026-10-29 | #759 at 75d2ac8b | Trim + Preferred + Undo at 1440 and 390 | One toast and Undo PASS; after Undo, Next: Cast is open on an over-cap song (FAIL) |
| 2026-10-29 | #759 at a7dd6a94 | Keep the first N lines (cap lowered to 300 to reach it; lyrics alone top out at about 629 credits) | PASS at 1440 and 390 (notes: end line, over_cap gate) |
| 2026-10-29 | #759 at 37344101 | Full song walk at 1440 and 390 (20 cases) | PASS; the screen holds the cap after a trim's Undo |
| 2026-10-29 | #777 at e52817cd (Final cut, Approvals words, back link) | Full browser suite; old links; no Ask the owner; no dollars; #751 kept | Flow PASS (52 passed); FAIL on the committed node_modules symlink |
| 2026-10-29 | #755 at 691a5eb5 (re-pass for the Producer) | Flow checks + no screen promises the unwired song checks (searched next, #759, #775) | PASS |
| 2026-10-29 | #748 at 6a97f0f, #750 at df64b78 | 15 API walk cases incl. trim → prefer → untrim → publish; full server suite | PASS (743 passed); cap bypass closed |
| 2026-10-29 | #778 at ef73d126, #779 at f1e883ee (Next-Layout) | Full browser suite each; price-first slot; shape confirm; small words | Flow PASS (52 passed each); FAIL on the node_modules symlink; VS1 shape gap raised |
| 2026-10-29 | #783 at b06193d4 (Suno input, one-song retry) | one-song, the 893 style limit, `[Lip-sync]` not sent, earlier API cases | PASS (notes: raw 422, plural wording) |
| 2026-10-29 | #781 at bcc1c1e7 (V2a screens) | Playwright at 1440 and 390 + song.e2e | FAIL: delete own take refused with a press that doesn't exist; the rest pass |
| 2026-10-29 | #750 at 837b659b | V2a API cases + delete a take the video made | Cap holds; FAIL: deleting a video's own non-song take gives 409 "Preferred" |
| 2026-10-29 | #750 at fd599553, #783 at f8a3199a | Delete a video's own take; 893 style message; one-song wording | PASS |
| 2026-10-29 | Next-Layout heads #766 5f5cb3bb, #771 e2a1defd, #773 4a6152a9, #777 98752ad8, #778 3b783a65, #779 9755e861 | node_modules symlink and .gitignore | PASS: no symlink on any; .gitignore fixed (5 of 6, #766 never had the link) |
| 2026-10-29 | #783 at 9bf8afbc (carries the V2a delete fix after #750 merged) | V2a, cap, un-trim API cases | PASS (14) |
| 2026-10-29 | #783 at 9bf8afbc | Try again prices: one-song quoted 0, charged 0; whole request quoted 1, charged 1 | PASS |
| 2026-10-29 | #759 at 16b9f166, #775 at bd184249, #781 at 2a3751ca | Full browser suite each (54/54/55 passed) + song walk 18/18 + V2a at 1440 and 390 | PASS |
| 2026-10-29 | next (10+ brands, Producer's ask) | Switcher, landing brand, New brand, archive + Restore with 14 and 32 brands at 390 and 1440 | PASS: no screen problem; the suite failures were test setup (remembered last brand; Restore past 25 rows) |
| 2026-10-29 | #780 at 02728f5e (flows LW3 Redo this frame) | Paper | PASS, 4 states to name (rewrite ok/draw failed, Undo both, over budget, shot vs clip) |
| 2026-10-29 | #785 at fa4261df (main into next) | Full browser suite | PASS (52 passed, 1 skipped) |
| 2026-10-29 | #780 at 176ab254 | The four states named (drawing fails after rewrite, Undo both, limits, shot; Redo the changed frames) | PASS |
| 2026-10-29 | #794 at dc146653 (song pilot follow-ups) | Story prompts identical; 32 tests; sounds-like handling | PASS (note: the artist name in the style is Advice, better as a fix) |
| 2026-10-29 | #799 at 1a1ac61e (song timing, re-flow) | Re-flow free; Undo exact (7/7); effect on clips | FAIL: clips not marked out of date after a song switch |
| 2026-10-29 | #802 at db5c0c58 (video takes never Preferred) | V2a API cases | PASS (6/6); #799 at dc121c63 still has the clips-not-out-of-date FAIL |
| 2026-10-29 | #799 at 51f7525e (re-flow by the line clock; old clips out of date) | A to B to A three times: times exact each round; clips made on A are Out of date on B and current again after Undo; a clip made on B is Out of date back on A; Timing guessed shown; 765 server tests, ruff | PASS |
| 2026-10-29 | #800 at its head (data.md: song part beside the plan) | Matches #799 | PASS (note: between lines an edge is placed by share, not always on a word edge) |
| 2026-10-29 | #799 at a7cb3567 (an edit repacks the song shots) | Delete a middle shot and Undo; two deletes and Undo; add a shot; delete the first or last shot | FAIL: delete the last shot, then Undo: the last shot comes back 0 seconds long, no problem shown. A reorder (API only) gives 0-second shots too |
| 2026-10-29 | #799 at 106e9061 (Sung clips out of date on any take change) | Same 12 checks | FAIL: same last-shot Undo state; the other 11 pass |
| 2026-10-29 | #810 at 50859f17 (take video cost, Delete on own takes, clips note) | Full suite + Change song walk at 1440 and 390 (57 passed); vitest 201 | PASS; fix expected: the cost isn't rounded (`wholeCredits`) |
| 2026-10-29 | #810 at e2efd06b | The cost rounding fix | PASS |
| 2026-10-29 | #799 at 8e20e1fa (a stretch is never a shot's own time; 0.5 s floor) | 15 checks: last-shot Undo, last two shots, one-step Undo, reorder, song switch | PASS (14/15); a reorder's Undo is not exact, API only |
| 2026-10-29 | #781 at 9ad11b40 (next merged in) | Full browser suite (55 passed) + V2a walk at 1440 and 390 | PASS (the Delete interim stays until #802) |
