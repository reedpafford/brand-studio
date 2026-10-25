# Workflow v2: server plan

Plan only. Nothing here changes how generation works: providers, the prompt pipeline and the worker stay as they are. Source: Reed's 2026-10-25 entry in `ops/DECISIONS.md`.

## The idea in one paragraph

A **script** becomes a thing of its own, owned by a brand and kept in the Script Library. It has up to three **versions**: the original plus up to two variations. Each version's words are locked once approved, and each can carry a saved breakdown. **Character locks** are kept per script. "Start production" on a version creates today's **project** from it, at most once per version. From there the existing flow runs (assets → storyboard → clips → final video). So the project model stays, and scripts sit in front of it.

## 1. Data model

New tables. All have `id` and `created_at`.

| Table | Fields | Notes |
|---|---|---|
| `scripts` | `workspace_id`, `brand_id`, `title`, `description`, `reference_id` (catalogue reel or null), `reference_replace`, `notes`, `created_by_id`, `status` | `status` is worked out, not stored: draft / published / in production / done. |
| `script_drafts` (a version; named apart from today's `script_versions`) | `script_id`, `kind` (original / variation), `slot` (0 = original, 1, 2), `text`, `status` (draft / approved), `approved_at`, `approved_by_id`, `target_seconds` (null = the breakdown decides), `breakdown` (JSON, the saved Breakdown or null), `breakdown_problems` (JSON), `breakdown_edited` (bool), `variation_note` (what changed, from Claude), `job_id` (the variations job that wrote it) | Unique on (`script_id`, `slot`). Words can change only while `status = draft`. Edits keep a history row (as today's ScriptVersion does), so nothing is lost. |
| `script_character_locks` | `script_id`, `library_item_id`, `sheet_file_id` (the approved sheet at lock time), `locked_by_id` | Unique on (`script_id`, `library_item_id`). The sheet is copied at lock time, so a later re-draw doesn't change locked videos. Unlock = delete the row. |
| `projects` (existing) | adds `script_draft_id` (nullable, **unique**) | One project per version: the "produced once" rule is a database constraint. Projects made the old way keep `null`. |

Changes to existing tables:

- `projects.planned_seconds` becomes nullable. Null means "the breakdown decides" (see §4).
- Today's project script history (`script_versions`, `script_suggestions`) stays. A project made from a version starts with that version's text as its script v1 (`source = "library"`), and the Enhance and edit history keeps working.

Migrations, one linear chain after main's head (0021 today):

- **0022_scripts**: `scripts`, `script_drafts`, `script_character_locks`.
- **0023_project_from_script**: `projects.script_draft_id` (unique, nullable) and `planned_seconds` made nullable. No data moves.

## 2. API

Everything is in the caller's workspace, and another workspace gets 404 (`assert_hidden`). No dollars appear for editors (`assert_no_dollars`). Paid steps use `BS_GENERATION_ENABLED`, are estimated first and have a duplicate guard.

**Library**

- `GET /scripts?brand_id=&status=&q=&min_seconds=&max_seconds=&reference=&versions_left=`
  - Returns the list for the Script Library.
  - Each row: `title`, `brand_id`, `reference_id`, `status`, `versions` [{`slot`, `status`, `seconds` (from the saved breakdown or the target), `produced` (project id or null), `video_ready`}] and `versions_left`.
  - `q` searches the title, description and script words.
- `POST /scripts/bulk`: up to 50 `{title, description, brand_id, reference_id?, text?}` at once, all-or-nothing, with a plain error naming the row.
- `POST /scripts`, `GET /scripts/{id}`, `PATCH /scripts/{id}`, `DELETE /scripts/{id}`.
  - Delete is allowed only while nothing has been produced; otherwise it archives.

**Versions**

- `PUT /scripts/{id}/drafts/0`: write, paste or upload the original's words. Adapting from the reference reuses today's draft step, writing into slot 0.
- `POST /scripts/{id}/enhance`: today's Enhance, on slot 0 (Reed's words never change).
- `POST /scripts/{id}/variations/estimate`, then `POST /scripts/{id}/variations` `{count: 1|2, note?}`.
  - One paid Claude job (write-claude, about 3 credits) with the Director's prompt. It fills empty slots 1 and 2.
  - Duplicate guard: 409 while one is running.
- `PUT /scripts/{id}/drafts/{slot}`: edit the words, draft only. 409 once approved: "These words are approved and can't change."
- `POST /scripts/{id}/drafts/{slot}/approve` locks the words.
- `POST /scripts/{id}/drafts/{slot}/regenerate` `{note}` (draft only; paid; replaces that slot only).
- `DELETE /scripts/{id}/drafts/{slot}` (a variation, draft only).

**Character locks**

- `POST /scripts/{id}/locks` `{library_item_id}`: the item must have an approved sheet (422 "Approve Maya's sheet first."). `DELETE /scripts/{id}/locks/{item_id}`.

**Breakdown preview** (optional, per version)

- `POST /scripts/{id}/drafts/{slot}/breakdown`: today's breakdown job, run on the version's words, with the script's brand, locked cast and reference. The saved result goes on the version.
- `PUT /scripts/{id}/drafts/{slot}/breakdown`: save an edited breakdown (timing, shots, splits and joins are all just the Breakdown JSON). `check.breakdown` runs, and its problems are shown, never blocking.

**Production**

- `POST /scripts/{id}/drafts/{slot}/produce`
  - Needs the version approved and not produced yet (409 "This version already has a video.").
  - Creates the project:
    - brand, title, aspect, reference;
    - the version's words as script v1;
    - cast = the locked characters plus any other characters named in the words;
    - `planned_seconds` = target or null.
  - Then it starts the breakdown:
    - With a saved breakdown, that is copied in as breakdown v1 (`source = "library"`), free.
    - Otherwise the breakdown job is queued automatically (paid, about 3 credits).
- **Assets step** (on the project, reusing sheets):
  - `GET /projects/{id}/assets` lists every character and place in the breakdown with:
    - `locked` (preloaded from the lock's sheet, nothing to do);
    - `sheet_status` (today's: none / drawing / waiting_for_owner / needs_approval / approved).
  - Unlocked ones are drawn with today's `POST /library/{kind}/{id}/sheet` and approved with `/sheet/approve`.
  - Storyboard and takes already refuse until every sheet is approved, so nothing new is needed there.
- **Final video**:
  - `POST /projects/{id}/video` (today: stitch the picked takes);
  - `PUT /projects/{id}/video` `{file_id}` (new: attach an edited cut uploaded through `/files`).
  - Either one marks the version done in the library.

**Variations job, input and output** (to agree with the Director; the prompt is theirs)

- Input:
  - the approved original's words (numbered);
  - the brand block;
  - the locked cast;
  - the reference summary, if any;
  - `count`;
  - an optional note from Reed.
- Output schema `ScriptVariations`: `{variations: [{script, change_summary, payoff}]}`.
  - The same story arc, with scenes, beats, lines and payoff allowed to change slightly.
  - Mechanical checks: house format, the brand end line, length within ±30% of the original's spoken words, and no locked character removed.

## 3. Roles

| Action | Owner | Editor |
|---|---|---|
| Write or edit their own scripts and versions, enhance, breakdown preview | yes | yes (their own scripts) |
| Make variations, lock characters | yes | yes on their own scripts; on the owner's, no |
| Approve a version's words | yes | their own scripts only |
| Publish to the library (visible to the team) | yes | yes for their own; the owner can unpublish any |
| Produce any published version | yes | yes |
| Edit or delete someone else's script | yes | no |

"Editors run the full flow inside their credit limits with no extra approval" maps onto today's rules like this:

- **Projects:**
  - The budget is still 2× the estimate, and the per-video cap is still 729 credits.
  - A project from the library starts **active**: no length approval (there is no length limit any more since #109).
  - Inside the budget nothing waits.
  - Going over the budget or the cap is the same held-for-owner path as today. That is the only time the owner is asked.
- **Script-side Claude steps** (variations, regenerate, breakdown preview) aren't tied to a project. They come from the editor's **weekly allowance**, like Quick clips (about 3 credits each). Past the allowance they wait in Approvals, as today.
- **Owner:** never held, as today.

## 4. Long videos

What stops long ads today:

1. `planned_seconds` is required (1–3600). The budget is `2 × planned_seconds`, so a wrong guess either blocks the run or over-budgets it.
2. A clip is 4–30 s (Seedance limit), so length only means more clips. There's no clip-count cap, and the breakdown fills clips up to 30 s.
3. The per-video cap is 729 credits. At 480p that's 729 s of clips per pass, so about 360 s (6 min) with one full redo.
4. The stitch runs in the request and is fast (about 20 s for 150 s with cut-ins). It's fine up to several minutes.

How length becomes optional:

- `planned_seconds = null` until a breakdown exists. After that, `estimate = sum(clip seconds)` from the newest breakdown, and the budget is 2× that, still never above the 729 cap.
- Before any breakdown, only Claude steps run. They're paid from a small fixed budget (e.g. 30 credits), so a project can always reach its breakdown.
- If Reed sets a target, the breakdown is asked to fit it (it's already in the brief text), and the estimate uses the target until a breakdown exists.
- The 729 cap stays the hard stop. `GET /projects/{id}/estimate` (#126) already shows credits left per stage, so an editor sees early when a long ad won't fit a redo.

## 5. What moves from today's project model

- **Nothing breaks:** old projects keep `script_draft_id = null` and their own scripts, breakdowns, storyboards and clips. Every existing route keeps working.
- **"New project" today** stays available as a shortcut. It creates a script with only slot 0 and produces it right away, so there's one path through the code.
- **Reference reels** (#153) move to the script (`reference_id`, `reference_replace`). The project keeps a copy, as now.
- **Enhance** stays on the project for old projects and runs on slot 0 for new scripts. It's the same code with a different target.
- **Brief fields** (goal, platform, aspect, product variant) are copied from the script onto the project at produce time. The project's own fields stay, for old projects.

## 6. PR order

Each PR is small, has tests, and regenerates `schema.d.ts` where the API changes.

| # | PR | Size |
|---|---|---|
| 1 | Migrations 0022 and 0023, models, and `planned_seconds` optional (budget from the newest breakdown; fixed pre-breakdown budget) | S |
| 2 | Scripts and versions CRUD, word locks, history, roles; `GET /scripts` with filters and search | M |
| 3 | `POST /scripts/bulk` | S |
| 4 | Character locks | S |
| 5 | Variations job (estimate, run, regenerate) using the Director's schema; allowance billing | M |
| 6 | Breakdown preview on a version (run, edit, save) | S |
| 7 | Produce from a version (project created, breakdown copied or run, one per version) | M |
| 8 | Assets step listing (locked or unlocked, sheet status) | S |
| 9 | Final video attach (`PUT /projects/{id}/video`), plus library status "done" | S |
| 10 | "New project" shortcut through scripts; `fake_run` updated to go through the library | S |

Every PR keeps `scripts/fake_run.py` green.

- **Dependencies:** PRs 1 → 2 → (3, 4, 5, 6 in any order) → 7 → (8, 9) → 10.
- **ETA:** about one working day of agent time for all ten, with PRs 1, 2 and 7 the longest. Builder-Screens can start the library list once PR 2 is up.

## Open questions for Reed

1. Should an editor be able to see and produce from the owner's **unpublished** scripts? Planned: no, only published ones.
2. Once a version is produced, can its saved breakdown still change for that video? Planned: the project gets its own copy, and the library version stays as Reed approved it.
3. Variations job billing: planned from the weekly allowance for editors. Should Reed's own variations show in Spend like other owner calls? Planned: yes, as usage, with no approval.
