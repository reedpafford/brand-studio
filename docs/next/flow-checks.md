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
| Song breakdown edit (#799, API only, not blocking) | After a reorder through the API, putting the plan back is not exact (1.1 0–12.58; 1.2–1.4 at 0.39 s). No screen reorders shots | Skip times from a row whose order differs, if a reorder ever reaches a screen | #799 at 8e20e1fa |
| S4 B (rule 4) | The decline past the week says "N free credits" (credits.over_allowance, also on main) | Drop "free" | #748 at 9a44a675 |
| Owner's plan vs an older preview (#934) | Fixed at 90b344d5 (the old preview isn't landed; the shots film the plan), but the version still says has_breakdown, so Make this version reads "Starting is free" and charges ~3 credits | has_breakdown only when the preview follows the approved plan |

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
| 2026-10-29 | 03:50 check-in: #783 at dd8efec0 (next merged in), #777 at 87f75a6c (next merged in), #773 at 4a6152a9 | Song API walks (71 of 72; the one miss is my old S4 U setup), no node_modules link | PASS; #814 is a tool and docs, no app flow |
| 2026-10-29 | #816 at c7a06758 (S2 length at the pilot's pace; S3 Write 2 song directions, hidden until the route) | Code and vitest (208), tsc, eslint | FAIL: Use this one drops unsaved typing though it says "kept in Undo"; Replace doesn't say takes go out of date |
| 2026-10-29 | #818 at c3960556 (S3 server: write, use, keep, remove) | API walk on stand-ins: write, Remove/Undo, Write 2 more, empty About, editor over week, failed job, approved version, Undo of Use | FAIL: Undo of Use leaves the claims note; on an approved version the paid press works but Use is refused |
| 2026-10-29 | #819 at a6867f29 (Director: names out of the style line; study copy check) | Code paths; name removal on 6 inputs; test_song (16) | FAIL: nothing calls the new checks (not #818 either); lowercase names kept; leftovers like "pop , upbeat" |
| 2026-10-29 | #816 at 41c3b02a | Unsaved typing kept in Undo; takes sentence; vitest 210, tsc | PASS on both; the refusal reason is still dropped |
| 2026-10-29 | #816 at 3e288df5 | Refusal reason; song price on Make this version | Reason PASS; FAIL: the press now shows the take's cost (no looks for uncast roles), under the version's price (40 → 34 in its test) |
| 2026-10-29 | #816 at 5c4a1cb8 | Price change reverted; only the song step files | PASS |
| 2026-10-29 | #819 at 00c4f96b | Name removal on 9 inputs (lowercase, leftovers), length note at minute edges, test_song (18) | PASS; note: a one-word song title ("Happy") also drops that word from the style. Wiring waits on #818 |
| 2026-10-29 | #818 at 6d9f12f9 | Same 6 API checks + the PR's tests (12) | Both fails fixed; FAIL on wording: approved says "Duplicate it", but Duplicate shows only once published (the way on is Undo approval) |
| 2026-10-29 | #825 at 6e0ca043 (Usage: archived first) | Sort before paging; test_usage (7), storyboard vitest (42); no node_modules link | PASS |
| 2026-10-29 | #826 at 75d7016b (V2: song times, Sung/B-roll, Timing guessed on shot rows) | vitest 499, tsc, Playwright auth+song (7) | PASS; notes: Needs timing / Timing guessed get their press when Snap lands; a sub-second shot reads 0:03–0:03 |
| 2026-10-29 | #828 at f3d3a576 (N1 narrator signal, V6n narrated prompts) | 18 house prompts byte-identical; narrator on 12 scripts; test_narrated (3) | FAIL: title-case dialogue ("Mia: …") reads as narration; not wired yet |
| 2026-10-29 | #818 at 2911002c (next in; one price; stop kind) | Song API walks + 4 song test files (74/75, the miss is my old setup) | One price PASS; still FAIL on "Duplicate it"; note: `video_credits` ignores a saved breakdown |
| 2026-10-29 | #828 at b596b1b8 | Narrator on 14 scripts; test_narrated (3) | PASS; note: prose lines like "Day One: …" make it a story video (safe side) |
| 2026-10-29 | #829 at 81fcf9ec (V6: Make video for a song video, n02) | Tests (15); switch to a 40 s take then Make video | FAIL: Make video uses clips made for the old song (24 s cut, new song under it, says current) |
| 2026-10-29 | #831 at 08545fe2 (only real names leave the style) | 14 inputs; test_song (19) | FAIL: "country Taylor Swift" keeps the name; "beatles" leaves "like the" |
| 2026-10-29 | next red since #821 (Assets tick test) | Bisected: each side passes, the merge fails; test kept a detached Steps list | Fixed on next by #832 (my #835 closed as duplicate) |
| 2026-10-29 | #818 at 6252911a (wording; names and one rewrite in the job) | 19 checks: names out (3 inputs), fake:three (one rewrite, charged once), fake:three-always (failed, not charged), approved wording, earlier states | PASS; S3a's copy check waits for the study route |
| 2026-10-29 | #842 at 6695ab56 (KIE adapter for Suno, off) | Off unless BS_KIE_SUNO and KIE_API_KEY; no key in code; mocked network; song tests + my song walks | PASS |
| 2026-10-29 | #831 at d510f8e5 | 18 inputs (name after a genre word, "the", lowercase bands); test_song (20) | PASS |
| 2026-10-29 | #829 at 88bbf0ad, #818 at 58d5c209 | Song switch to 40 s then Make video (409, way on), rewrite + remake (40.07 s, current); #818 next merged only | PASS both; note: "1 of the clips were" |
| 2026-10-29 | #851 at 8fcccdbf (S3a song-ad study, free) | Upload done; busy 409; cancel; blocked link; re-study after a done one; approved version; lyrics untouched | FAIL: a failed re-study deletes the finished study (frames dropped at start), no Undo |
| 2026-10-29 | 05:44 check-in: #853 at cccf5fcb (narrated sound, music bed, narrator on the format); #777 at 10d7805f (next merged in) | 19 of 20 house prompts identical; narration_text, format_advice, music check; test_narrated (7) | #853 FAIL: "no vocals" / "without any singing" flagged as asking for a voice; #777 no change, no link |
| 2026-10-29 | #857 at c4819084 (S3a screen: Study a song ad) | Code and vitest (221), tsc, eslint | PASS; notes: "couldn't open that reel" for uploads too; no Stop while running; must show a failed reason above a kept study once #851 is fixed |
| 2026-10-29 | #857 at 05291860 | Failed wording | PASS: "We couldn't study it: …" for links and uploads |
| 2026-10-29 | #851 at c2f558c0 | Failed re-study over a done one; good re-study; cancel over done and first; Remove/Undo; tests (12) | PASS; #857 follow-up shows `attempt` above the kept study |
| 2026-10-29 | #862 at af72f9ce (P3 automatic fixes) | test_clip_takes (13); Make clip while retry waits; edit prompt while retry waits, then let it run | FAIL: the waiting retry runs the old prompt, charges 5, take shows current |
| 2026-10-29 | #853 at 55c50456 | Music check on 11 phrasings; test_narrated (7) | PASS; notes: "no vocals but a choir sings" not flagged, "vocals-free" flagged |
| 2026-10-29 | #863 at 7929c28c (P3 screen: retry line, Fixed for you + Undo) | Code and vitest (303), tsc; Undo after an edit | FAIL: auto_fix survives an edit (#862), Undo 409s and the card says "try again" forever |
| 2026-10-29 | #858 at 237f6527 (N1 narration step 1) | test_narration (6), song regressions (73/74, my old setup), publish with old narration, editor over week, quote vs charge, double press | PASS; notes: double press makes two narrations; wording; ~0.06 shows "free" |
| 2026-10-29 | #864 (real Suno on the test site) | Not walkable until Reed sets the key; no paid call from Flow-QA | — |
| 2026-10-29 | #865 at 0324c487 (cost bar, part 1) | vitest 718, tsc, Playwright full at 1440 and 390 (55 passed, 1 skipped) | PASS |
| 2026-10-29 | #863 at 3eb91b26 | Undo shows the server's reason | Half fixed; waits on #862 clearing auto_fix on an edit |
| 2026-10-29 | #862 at b4d3ef79, #863 at 3eb91b26 | Edit (inside a Shot line) while the retry waits: retrying null, retry cancelled, 0 charged; fix then edit clears auto_fix, Undo 409 with reason | PASS both |
| 2026-10-29 | Live finding (main and next) | Words added after the closing "Audio:" line of a clip prompt: PUT reply keeps them, the next GET drops them (clip_prompts.repair on the list) | FAIL, to the Producer for an owner |
| 2026-10-29 | #868 at d756188d (main: words after the audio line kept) | Repro: save, 3 loads (kept once, stable), edit the moved words; clip tests (23) | PASS; note: the words move above the Keep line on the next load |
| 2026-10-29 | 06:37 check-in: #866 at 03ddd719 (Director: scene plan P1) | 20 house prompts identical; check.plan on a sample (missing, order, twice); tests (112) | PASS; notes: narrated "sentences" vs script lines; "lines 1 are"; not wired yet |
| 2026-10-29 | #866 at 6185531b | Narrated lines whole; "line 4 is" | PASS (nit: "lines 1, 2 are not a script line") |
| 2026-10-29 | #871 at 15127e2e (new step order: Plan · Cast · Storyboard · Clips · Final cut) | vitest 732, tsc, Playwright full at 1440 and 390 (55 passed, 1 skipped); old links | FAIL: problems and a link still say "Approve … in Assets"; the step is Cast |
| 2026-10-29 | #851 at b01bbc99 (next merged in, n04 after n02) | One alembic head; study, directions, final cut tests (24) | PASS |
| 2026-10-29 | #873 at 8e86ba8a (Format and Look step 1: ST1, ST3, VS1) | test_looks (4); code read for VS1 | FAIL: a video's look change marks nothing out of date (same as VS1 Shape); "ask the owner" in the editor's message |
| 2026-10-29 | #871 at 699c1e47 | Messages and link say Cast; server tests (15) | PASS |
| 2026-10-29 | #873 at 2be90844 | Look change: stills and clips out of date, redo price, Make video 409, Undo restores; Off message; tests (25) | PASS; n07 must be re-pointed to next's newest migration before merge |
| 2026-10-29 | #875 at 88a6a377 (S3a Stop and 10-minute limit) | test_song_study (12); code read | PASS; notes: #857 needs Stop while running; Stop-vs-finish race |
| 2026-10-29 | #858 at 013e8492 (next merged in, n05 after n04) | One alembic head; narration, study, song tests (38) | PASS |
| 2026-10-29 | #876 at 236474b9 (P1 Plan step, part 1) | Code and vitest (740), tsc; hidden without plan_status | PASS; notes: price from the route's estimate once it lands; no Stop while running |
| 2026-10-29 | #862 at 211a8ea8 (next merged in) | test_clip_takes (14) | PASS; n06 and #858's n05 both follow n04: re-point the second |
| 2026-10-29 | #877 at a5f19e45 (cost bar part 2: Clips) | vitest 733, tsc, Playwright full at 1440 and 390 (55 passed, 1 skipped) | PASS |
| 2026-10-29 | 07:30 check-in: #875 at 2c4466ea (race), #877 at 567b8cac (rewrite waits for its price), #873 at fc0725a7 and #866 at 0ffd2499 (next merged in) | test_song_study (13), test_looks (5), test_plan (5) | PASS all; #873's n07 now also follows n04 |
| 2026-10-29 | #869 at 7950de1b (Director: P4 advisory check, P3 on-screen text fix) | 21 house prompts identical; text_on_screen on 7 phrasings; tests (107) | FAIL: "No captions, no text overlays", "without any on-screen text", "No text on screen" stripped and reported as fixes |
| 2026-10-29 | #878 at 134233b2 (main: the save puts the words where they stay) | Repro: PUT == GET, stable, once; Shot edit; tests (14) | PASS |
| 2026-10-29 | #879 at 6b00f7be (Stop on the study card, attempt failure above a kept study, tenths, no_facts lifts) | vitest 535, tsc | PASS; merge #875 first or with it |
| 2026-10-29 | #858 at 2055786a (next merged in) | test_narration, test_song_takes, test_kie, publish with old narration (36) | PASS |
| 2026-10-29 | #781 at 9ad11b40 (next merged in) | Full browser suite (55 passed) + V2a walk at 1440 and 390 | PASS (the Delete interim stays until #802) |
| 2026-10-29 | #869 at e1e94cd2 (safeguards stay) | text_on_screen on 6 phrasings; test_item_check | PASS: "No captions…", "without any on-screen text", "No text on screen" unchanged; "bold text", "title card", "captions under her" removed |
| 2026-10-29 | #864 at bef43a05 (real Suno on the test site, test budget) | test_kie, test_song_takes (33); budget repros; deploy env | FAIL: a video put away mid-song stops counting toward the budget; "used up" note not on screen |
| 2026-10-29 | #858 at b068ef81 (narrator reads check.narration_text) | narration_text on 8 scripts; 153 narration/song/check tests with fix | FAIL: prose + "CTA:" line → nothing to read ("Write the words first"); one "Name:" prose line drops the rest; n05 still on n04 |
| 2026-10-29 | #883 at c998d91f (P3 retried, auto_fix.before) | test_clip_takes (14); stored auto_fix rows all carry before | PASS (screen: put "Tried again once on its own" by the newest take) |
| 2026-10-29 | #882 at a904afb9 (V6 song on Final cut) | code walk; take removal after a switch | FAIL: removing the final's take hides "now uses take N"; non-song videos fetch /songs (409 ×4) |
| 2026-10-29 | #882 at ca27118b (both fixes) | finalsong + videosong (13) | PASS |
| 2026-10-29 | #881 at adb76baa (cost bar: Storyboard) | Playwright 1440 + 390: empty, Approve all, Redraw in bar; vitest projects (317) | FAIL: while Redraw is in the bar, bulk "Make N stills" is hidden (over-budget redraw leaves only per-card presses) |
| 2026-10-29 | #885 at 3cef0f71 (S3a study link on the stand-ins) | test_song_study + test_reel_import (30); failure state on screen | PASS (walk on the test site once deployed) |
| 2026-10-29 | #864 at 6e0a4074 (both fixes) | test_kie + 2 budget repros (13); songs + videosong web (33) | PASS |
| 2026-10-29 | #887 at 350deb53 (narration_text: prose with a direction or "Name:" line) | 9 scripts; test_narrated (8) | PASS (edge for the Director: SCENE headings + one "Iron Paws:" line still drops prose) |
| 2026-10-29 | #886 at 80f9ec50 (P3: on-screen text out of clip prompts) | reword on 6 prompts; 18 tests | PASS (Director: quoted drawn text "big text \"SALE\"" is kept) |
| 2026-10-29 | #863 at 30eab39e (Undo fix, newest-take line) | autofixes + clips (34) | PASS (nit: "(busy)" raw code) |
| 2026-10-29 | #888 at b8050325 (Videos in the menu, homes) | Playwright 390 + 1440: homes, tab, back link, old link; shell + phone e2e (11) | FAIL: old ?view=videos link stays on Scripts (params mutated in render; StrictMode) |
| 2026-10-29 | #889 at 9e8e7e1f (Final cut banner names the song; one full stop) | finalsong + songstudy + downloads (17) | PASS |
| 2026-10-29 | #881 at 95e50919 (Make N stills kept grey; "The plan changed"; "1 credit") | vitest projects (321); step name check | PASS (old ProjectPage EstimateNote says "Breakdown", "1 credits": owner to delete or rename) |
| 2026-10-29 | #890 at 1914e0f0 (drawn words in quotes) | text_on_screen on 9 prompts; test_item_check (2) | FAIL: a shot that is only drawn text is emptied ("Shot 1 | 0-3 s."); on next since #869 (missed in my #869 walk) |
| 2026-10-29 | #891 at a1928c52 (P4 advisory check, server) | checking/ok/advice/Looks fine/review/skipped/failed; test_item_checks + migrations (6) | PASS (notes: a queued check holds 0.2 credits; check cost to show in Video settings before real checks) |
| 2026-10-29 | #888 at dca52d6a | Playwright 390 + 1440 again | still FAIL: old ?view=videos link stays on Scripts (fix not in) |
| 2026-10-29 | #893 at b7f56c4d (P1/P2 plan, server) | E, make, Stop, 10-min limit, Advice, edits, by hand, Earlier plans, approve, old video; test_plan_route + repro (4) | FAIL: after Earlier plans the shots from a newer plan aren't "Made for an older plan" (version reused) |
| 2026-10-29 | #890 at 6820b8f3 (no shot emptied; capital after a cut) | text_on_screen + advice on 5 prompts; test_item_check (2) | PASS (#886 must wire text_on_screen_advice on the fixed prompt) |
| 2026-10-29 | #896 at 18afb0e (Videos: Needs you, waiting_on) | code walk; test_needs_you (2) | FAIL: unnamed steps read "A step didn't finish"; a failed advisory check (with #891) would flag the video |
| 2026-10-29 | #888 at e2d2d666 (old-link fix) | Playwright 390 + 1440 | PASS |
| 2026-10-29 | #897 at 0a8380e5 (S3a: study used as a guide for directions) | guide on/off/removed; copied line → one re-ask → fail; 26 tests | FAIL: copied-line failure shows the general message; say why and "Try again, or turn off Use as a guide" |
| 2026-10-29 | #898 at c63dde4a (P1 web: edit, Stop, Earlier plans, Out of date) | code walk; plan + planEdits (17) | FAIL: "Update the plan" is a paid new plan promising kept scenes; Use this one on an approved plan has no confirm |
| 2026-10-29 | #901 at 47d1494e (ST0 format chip, ST1 look picker, "Music style") | code walk; vitest scripts (234) | PASS (hidden until #873; server still says "style line" in 3 messages; live walk after #873) |
| 2026-10-29 | #892 at e2a47360 (Director: breakdown films the plan; check.follows_plan) | prompt read; test_plan (6) | PASS (follows_plan not wired yet: with or after #893) |
| 2026-10-29 | #901 + next (#873) live | Playwright 390 + 1440: chip, picker, use, toast, Undo, server look | PASS |
| 2026-10-29 | #897 at 666b7028 (copied-line message) | test_song_directions (12) | PASS |
| 2026-10-29 | #858 at a6002245 (next + #887 merged; n05 → n07) | 3 narration scripts via narration.job; narration + narrated + migrations (17) | PASS |
| 2026-10-29 | #892 at 693e7cdd (plan rule in the message) | breakdown system prompts byte-identical to next; test_plan + test_prompts (115) | PASS |
| 2026-10-29 | #891 at 5092a41f (scope key_takes, check_credits_per_video, approved_with_advice) | item_checks + approve_all + migrations (8) | PASS (notes: estimate skips prop-only key clips; V.O. counts as speaking; approved_with_advice over all picked) |
| 2026-10-29 | #902 at 78aaa19e (P4 screens: notes chip, Review, summary) | code walk; vitest projects (328) | PASS (gaps owned: paused line, "approved with Advice") |
| 2026-10-29 | #896 at dda65d8a (advisory skipped, steps named) | test_needs_you (3) | PASS |
| 2026-10-29 | #898 at e9500ec3 (Make a new plan label; confirm on Use this one; toast) | plan + planEdits (18) | PASS |
| 2026-10-29 | #891 at 86d811d8 (check skipped if it would take the room for one more take) | item_checks + approve_all (5) | PASS |
| 2026-10-29 | #883 at c2a62e4f (merge of next) | clip_takes + looks (19) | PASS |
| 2026-10-29 | #905 at f0642ba4 (Approve all in the bar: Cast, Clips) | code walk; vitest projects (327) | PASS |
| 2026-10-29 | 10:16 check-in: merged #858 #881 #883 #888 #889 #890 #892 #897 #901 | — | — |
| 2026-10-29 | #902 at 54d460d9 ("N approved with Advice") | vitest projects (333) | PASS |
| 2026-10-29 | #896 at c27a69d0 (merge of next) | — | PASS stands |
| 2026-10-29 | #906 at 813934e2 (M14 part 1: out of date stays viewable, paid presses wait) | code walk; vitest projects (327) | PASS (wording: "redo the out-of-date stills" is cheaper than the whole storyboard) |
| 2026-10-29 | #907 at 07968de0 (narrated 2a: one narration at a time, ST0 switch, narrator check, narrated clip prompts) | narration + narrated + song_takes (41) | PASS |
| 2026-10-29 | #908 at 3afac6ce (ST2 banned words per look) | look_words on 7 prompts; styles + song (40) | FAIL: safeguards rewritten ("no blood, no gore" → "no glow, no ,"; "not floating" → "not resting"; "Not photorealistic" → "Not stylised") |
| 2026-10-29 | #906 at 03c0ad93 (archive lands on Videos with Undo) | vitest projects + videos (334) | PASS |
| 2026-10-29 | #909 at 29596fd2 (Narrated format: S1, N1, V6n screens) | code walk; vitest scripts + finalsong (243) | FAIL: Make another live while timing (server 409s) |
| 2026-10-29 | #910 at c70a64c (BR1 server: owner-only edits, CTA lines, defaults) | brand_setup + brands + migrations + variants (24); Look tab fields | FAIL: PATCH /brands is owner-only for all fields, so editors lose logo, colours, fonts, tone, never say, legal, end line (Look tab) |
| 2026-10-29 | #908 at 4643ed19 (negated matches skipped; not/never) | look_words on 7 prompts; styles + item_check + song (42) | PASS (notes: add "nothing"; a removal can leave "Notably .") |
| 2026-10-29 | #906 at 31aeab1b (merge with #905) | vitest projects + videos (336) | PASS |
| 2026-10-29 | #910 at 48072c78 (403 only for BR1 fields) | brand_setup + brands + variants (21) | PASS (Reed: editor never say/end line write through to BR1) |
| 2026-10-29 | #893 at 4d2b36f7 (one next version; follows_plan wired, leftovers as Advice) | version repro; plan_route + plan (10) | PASS |
| 2026-10-29 | #886 at 624a68da (text_on_screen_advice on the fixed prompt) | reword on 2 prompts; clip_takes + item_check (18) | PASS |
| 2026-10-29 | #909 at 04350686 (Make another waits while timing; "Wait for the narration to finish") | vitest scripts + projects (587) | PASS |
| 2026-10-29 | #912 at 6ba27460 (narration music bed, narrated mix) | code walk; narration + needs_you (18) | FAIL: no off switch for real Stable Audio (only generation_enabled); "Nothing was charged" wrong when the prompt succeeded and the bed failed |
| 2026-10-29 | #910 at 026f3b51 (merge of next) | brand_setup + brands + migrations (21) | PASS |
| 2026-10-29 | #914 at 7b944b0a (retry line in words; focus after Review and Change this…; params kept) | vitest projects (341) | PASS |
| 2026-10-29 | 11:09 check-in: merged #863 #891 #892 #896 #901 #902 #905 #906 #907 #908 #910 | — | — |
| 2026-10-29 | #913 at 2226ccb9 (Looks fine Undo, paused, truer estimate) | item_checks (4) | PASS |
| 2026-10-29 | #898 at 0756510f (Not yet keeps the editor; confirm names what goes out of date) | plan + planEdits (19) | PASS |
| 2026-10-29 | #893 at dd2fbb2d (merge; "Check the scene plan" in Needs you) | plan_route + plan + needs_you + migrations (15) | PASS |
| 2026-10-29 | #916 at 89a77563 (BR1 screens: voice, CTA lines, defaults) | code walk; vitest brand (29) | Producer: not intended; Next-Screens to give editors tone notes, never say and end line back (re-walk) |
| 2026-10-29 | #915 at 685c295f (Videos home groups; /projects → Videos) | Playwright 390 + 1440; vitest videos + projects (349) | PASS |
| 2026-10-29 | #917 at f9f32934 (M14 part 2 server: Update everything after this) | code walk; update_after + storyboard (11) | PASS |
| 2026-10-29 | #893 at 657174e6 (merge of next) | plan_route + plan + needs_you + migrations (16) | PASS |
| 2026-10-29 | #915 at 74550901 (Done label; earlier-way New video back link) | vitest videos + projects (349) | PASS (back to Scripts is right: the earlier-way list is on Scripts) |
| 2026-10-29 | #912 at a43c4046 (music off by default with a budget; true charge message; bed-only retry) | narration + needs_you (19) | PASS |
| 2026-10-29 | #893 at 9afd850a (★ with no product or screen: 409 with the way out) | plan_route + plan (9) | PASS |
| 2026-10-29 | #916 at 4133068a (merge of next after #910) | KitPage editor body | FAIL: editors still lose tone notes, never say, end line (Producer asked to keep them) |
| 2026-10-29 | #918 at 2e459e39 (ST2: look words fixed in clip prompts and stills, with Undo; look fixes offered) | look_words + clip_takes + item_checks + storyboard (30) | PASS |
| 2026-10-29 | #919 at 6960953a (ST0 Dialogue↔Narrated with Undo; narrator check; sentence times) | code walk; vitest scripts (250) | PASS |
| 2026-10-29 | #916 at e3af3c93 (editors keep tone notes, Don't/never say, End line) | vitest brand (29) | PASS |
| 2026-10-29 | #920 at 7e33b1a4 (N1: nothing to read → songs_note, price 0) | narration (16) | PASS server (screen must show songs_note as the press reason, else "· 0 credits" then refused) |
| 2026-10-29 | #898 at e5291fe2 (12:14 check-in) | PASS: a ★ with no brand product shows #893's 409 sentence once, with Add a product (Products tab, editors too); no toast, nothing saved; older-server fallback says the ★ wasn't kept. Follow-up: clear the ★ line on a non-409 error so a later refusal isn't hidden. #909, #912, #913, #915, #917 left the open list. #854 CI running |
| 2026-10-29 | #918 at f7a1d745 (next merged in) | PASS: the merge only touched imports; look words, narration and storyboard tests 26 passed |
| 2026-10-29 | #921 at 4af7948b; #918 at 574cb4c2 | #921 PASS for its own presses (Updating…, done, over budget, one press in the bar, Stopped at {step}); flow FAIL on #917's stop that outlives its fix (open below). #918 PASS (next merged in only) |
| 2026-10-29 | #898 at fc86b412; #916 at c4cadde9 | #898 PASS (next with #893 merged in; plan page unchanged; the non-409 note stays open, not blocking). #916 PASS: Default cast with no characters says so, with Add one in Cast & places |
| 2026-10-29 | #922 at 61c156c0 | PASS: a still redrawn with its own press clears the Stopped banner (Out of date → Open Clips comes back). New: a frame to fix first stops the run at Clips, not Storyboard (open above) |
| 2026-10-29 | #919 at 3bc09e40 | Narration with no words fixed (greyed, the reason, no price): that row closed. Music states PASS. FAIL: Try the music again past the editor's week (open above) |
| 2026-10-29 | #919 3bc09e40 + #920 7e33b1a4, merged together | PASS live at 1440 and 390: headings only → Make the narration greyed, no price, "Write the words first…"; Next: Cast says why, Back leads to the words; with words the narration and its music are made on the stand-ins |
| 2026-10-29 | #923 at 61aaf2c6; #924 at 711029ea | #923 FAIL: the earlier way's breakdown is refused with no Plan step (open above); new videos and old ones with a breakdown PASS. #924 PASS: every look's sample person passes its own word check |
| 2026-10-29 | #925 at 837642ba (VS1 server) | Prices, preview, Out of date and back, Sung ↔ B-roll, 403 for others' videos, Make video's refusal: PASS. FAIL: Undo refused over the cap (open above) |
| 2026-10-29 | #926 at 40919a9b (VS1 screen) | FAIL: its API shape isn't #925's (open above). Full walk once they agree |
| 2026-10-29 | #927 at ac0b65b6 (ST3 server) | Owner only, hero / pick / the look's own person, one price, second press refused, Switch on needs the clip: PASS. FAIL: Try again after a failed clip remakes the still (open above) |
| 2026-10-29 | #922 at e7aef548 | PASS: a frame to fix stops the run at the stills, "Fix shot 1.1 on Storyboard and draw it…" (Open Storyboard); drawing it clears the stop. The open row for it is closed |
| 2026-10-29 | #928 at 0acd4228 (P1 Change this scene, Update the plan) | PASS for both presses, their refusals and Earlier plans. FAIL: an edit during a scene change drops the paid result silently (open above) |
| 2026-10-29 | 13:17 check-in; #919 at 542db621 | #919 PASS: a format switch without the current step lands on Script. #898, #914, #918 merged. Open PRs into next: #916 #919 #920 #921 #922 #923 #924 #925 #926 #927 #928; none into main. Holding #923, #925, #926, #927, #928 (open above) |
| 2026-10-29 | #929 at 2d58eaa5 (ST2 screens, #898 follow-ups, #923's way on) | PASS: Undo only before the still is drawn; look tips; the #898 notes closed; Open the plan from the old page. FAIL: two one-line fixes (open above) |
| 2026-10-29 | #927 at 6733ab92 | PASS: after a failed clip, Make a sample makes only the clip from the kept still at the clip's price (5); ready, then Switch on works. Open row closed |
| 2026-10-29 | #922 at 2b352389; #930 at 6e35749e | #922 PASS: a stop waits on each still it named. #930 server PASS (sheets per look, Make a {look} look priced); FAIL with the screens: made work locked out (open above) |
| 2026-10-29 | #919 b798db49; #925 51f8258e; #926 91576f5a; #929 c825f460 | #919 PASS (paid retries wait past the week): row closed. #925 PASS (Undo never refused with undo:true): row closed. #926 shapes match #925; Undo flag still missing. #929 link dropped (fix 1 closed); fix 2 open |
| 2026-10-29 | #923 at 91e56824 | PASS: only a video made from a script waits for its approved plan; the earlier way makes its breakdown as before. Open row closed |
| 2026-10-29 | #932 at 7bc1f85a (BR1 product line and claim) | The prop page PASS (owner edits, editor read only with the reason, Advice). FAIL: no way there from the Brand page (open above) |
| 2026-10-29 | #927 at 5ae09626 | PASS: a still with no picture reads failed with the way on, never "making" for ever. Note: that job stays succeeded, so it's charged; fail it uncharged if the worker allows |
| 2026-10-29 | #928 at 750f4ecc | PASS: an edit while a scene change runs is refused with the reason; the paid scene lands, then the edit saves. Open row closed |
| 2026-10-29 | #929 at 7ae54fdb | PASS: Fixed for the look shows only while the prompt is the fixed one, so it goes after Undo. Open row closed |
| 2026-10-29 | #933 at 3cfb6d5c (P1 Change this scene, Update the plan screens) | Press, price, ask first, Update the plan: PASS. FAIL: the typed note is lost on Not yet or a refusal (open above) |
| 2026-10-29 | #934 at 116f2fd2 (S6, the owner's plan on a version) | Make, by hand, edit, stop, approve, read only once published, preview after approval: PASS. FAIL: a preview older than the plan is carried into the video (open above) |
| 2026-10-29 | #932 at 686cf621 | PASS: the Products tab links to the props in Cast & places, where each product's line and claim live. Open row closed |
| 2026-10-29 | 14:21 check-in; #925 51f8258e + #926 68522998 live | VS1 PASS at 1440 and 390: the row with prices, the confirm "To finish: about 22 credits (was 30)", Switch, Undo; over the cap 2.5 greyed, 2.0 fits, Undo back to Auto with no refusal; the phone sheet. Open row closed. Merged since 13:17: #916 #919 #920 #921 #922 #924 #927 #929. Holding #930, #933, #934 |
| 2026-10-29 | #933 at 7bb57251 | PASS: the scene note stays through Not yet or a refusal; a scene job shows Making the plan… with Stop. Open row closed |
| 2026-10-29 | #935 at c5de5658 (ST3 Looks page) | Owner only, House always on, make → making → ready → Switch on, failed → Try again, Switch off with Undo: PASS. FAIL: loading for ever with no brand (open above) |
| 2026-10-29 | #926 at 783f3554 (next merged in) + #925 | VS1 live walk again at 1440 and 390: switch, Undo, over the cap, the phone sheet: PASS |
| 2026-10-29 | #935 at a7891301 | PASS. My no-brand FAIL withdrawn: with zero brands the shell shows "No brands yet" in place of /looks, so it can't be reached; Make another sample keeps the picked character. Open row closed |
| 2026-10-29 | #936 at eb32ed12 with #930 at 724e0a9d | PASS: made work in another look stays open; its paid presses wait with "Waiting on the cast" and Open Cast. Open row closed. Follow-up (not blocking): hold #921's Update everything after this on the same cast line |
| 2026-10-29 | #937 at d997cb0b (languages list, VS1/BR1) | PASS: English on, others off; an editor's off language refused with the way on, the owner's allowed; unknown 422; brand default off → an editor's script starts in English; the check only on create |
| 2026-10-29 | #926 at 0cf5d8af (next with #925 merged in) | PASS: settings code unchanged; its videosettings.e2e 6 passed; over the cap, switch to fit and Undo back to Auto at 1440 and 390 |
| 2026-10-29 | #934 at 90b344d5 | The older preview no longer lands; the breakdown films the owner's plan. FAIL: its price goes unsaid ("Starting is free") (open above) |
| 2026-10-29 | #938 at 2d2f6b69; #939 at b9f5f06f | #938 PASS (test only, 3 runs green). #939 PASS: a refused Update everything after this says why and stays pressable for a retry after a fix elsewhere; note: clear the old reason when the price changes |
| 2026-10-29 | 15:40 check-in | Every open head already walked. Merged since 14:21: #923 #925 #926 #928 #932 #933 #937 #938. Open into next: #930 + #936 (PASS, merge together), #935 PASS, #939 PASS (cast-line follow-up coming), #934 held ("Starting is free" while charged). None into main. #854 green |
| 2026-10-29 | #941 at 2dd9a08b (Make this version makes the plan first) | PASS: plan first at the quoted price, declined call undoes the project, failed plan's way on, song.e2e live. FAIL (words): "(the breakdown)" on the panel (open above) |
| 2026-10-29 | #942 at 0efd0f47 (web side of #941) | PASS: the panel says the plan is made first; the toast says plan or shots. #941's words row closed. Note: the price line says "(the plan)" for an owner-plan version too |
| 2026-10-29 | #941 at 6deca1bb + #942 0efd0f47 | PASS together: #941's own wording backed out, #942 carries it; they merge cleanly |
