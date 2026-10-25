# Workflow v2: the Director's part (plan, not built)

Owner: Director. Status: plan for the Producer and Reed to approve. Nothing here changes generation until it is approved. Source: ops/DECISIONS.md, 2026-10-25.

Two pieces: **1. Variations** (a new prompt step) and **2. no check is ever a dead end** (including the montage check fix).

---

## 1. Variations

Reed approves his enhanced script, then asks for 0, 1 or 2 alternates. Each one tells the same story a slightly different way. His original never changes. New words appear only in the variations. Editors can do the same with their own approved scripts (#190), so the prompt works on any approved script, not only Reed's.

Reed's example: the altar reel becomes "she says hell no to a car he gifted, leaves with a richer guy, flashback of her saying she didn't care what she drove". It has the same arc and a payoff that fits.

### Input (what the server sends Claude)

Step name `variations`. The system prompt is `rules.md` + `variations.md` + a worked example. The user message contains:

| Tag | What |
|---|---|
| brand block | as today: tone, never-say, end line, required screens and product, moments |
| `<script>` | the approved, enhanced original, numbered |
| `<cast>` | the locked characters (char ids and names); each one stays in every variation |
| `<length>` | the original's spoken words and estimated seconds (words ÷ 4.8) |
| `<reference>` | optional: the reel the original adapts (live-action shots already removed) |
| `<count>` | 1 or 2. With 0 there is no call. |
| `<keep_apart>` | optional: the other version's script, when regenerating one variation, so the new one differs from it |
| `<note>` | optional: Reed's note for this regenerate ("make the gift a watch") |

### Output (what Claude returns)

The exact output schema lives in Builder-Server's plan (#189), and that file is the source of truth. This doc doesn't copy it, so the two can't drift. It holds exactly `<count>` items in slot order (1, 2), with no id: a title (2–4 words, for the library), the script in house format, and a short plain-language account of what changed and how it pays off. A regenerate replaces one slot, with `<keep_apart>` and `<note>`. Builder-Server stores each variation as a draft version and never writes to an approved one. The prompt and checks will use whatever field names #189 has when it merges.

### Rules (variations.md)

1. **Same high-level story.** Same arc (setup → turn → payoff), same main character and the same role for each character. The scenes, beats, lines, props and payoff may change to fit the new premise. A variation is a new take, not a reword: its premise must differ from the original's and from the other variation's.
2. **Engaging.** Both of our creative rules apply. The first second hooks, and the house story shapes and cut rhythm still hold.
3. **The brand, kept.** Every required moment in the original is in each variation, with its `★` line and the same screen or product. The video ends on the brand's end line, word for word.
4. **Live action never comes back.** If the original adapted a reel, its live-action slot is the end line in every variation.
5. **Montages** follow the montage rules: the hero is in every shot, and the wealth payoffs build, he's part of them, and they're invented for this story.
6. **Roughly the same length.** Spoken words within ±30% of the original.
7. **Words.** The original's words are untouchable. A variation's words are new, but they don't copy the reference reel's on-screen text, and they never say anything the brand's "never say" list forbids.
8. **The locked cast stays.** Every locked character is in every variation, in the same role.

### Checks (`check.variations`)

Each one says what to do next (see part 2 for fix vs advice).

| Check | Kind | Way forward |
|---|---|---|
| wrong number of variations | fix | regenerate |
| a variation doesn't end on the end line | fix | edit the last line, or regenerate |
| a required moment's ★ line or screen is missing | fix | edit, or regenerate |
| a `never say` phrase appears | fix | edit, or regenerate |
| a live-action tag or segment appears | fix | edit, or regenerate |
| a locked character is dropped | fix | edit, or regenerate |
| spoken words outside ±30% of the original | advice | keep anyway, edit, or regenerate |
| too close to the original or the other variation (over 70% shared words) | advice | keep anyway, or regenerate with a note |
| house format: a line isn't a scene heading, an action, `NAME: words` or a ★ line | advice | keep anyway, or edit |

The original's text is protected on the server, not by Claude. Builder-Server never writes to the original version once it's approved.

### Eval cases (in `server/evals/cases.json`)

- **`fomo-altar-variations`**
  - Input: the approved altar remake (the done-test script), count 2.
  - Expected: both end on fomo's end line, both keep the fomo trading screens and the montage, both are within ±30% of the original's words, the two premises differ, and neither copies the original's lines wholesale.
  - Human check: does each one play the same arc with a payoff that fits?
- **`ironpaws-pitbull1-variations`**
  - Input: Pitbull 1 (voiceover, peanut-butter bag), count 1.
  - Expected: it stays voiceover, keeps the PB bag ★ line at the feeding moment, stays within ±30% of the original's words, and never names the chicken flavour.

### $0 dry run (no paid calls)

1. **Worked example:** `examples/variations.json` is a fomo variation written by hand. A unit test runs `check.variations` on it, as we do for every step today.
2. **Unit tests** for each check, both pass and fail.
3. **Rendered prompts:** `evals/run.py --print` writes the exact system and user messages for each case to disk without calling Claude, so the Producer can read what would be sent.
4. **Free stand-in:** Builder-Server's stand-in writer (`fake_local`) returns a deterministic variation that passes the checks, so the whole flow runs end to end for free.

**Estimated paid eval:** 2 cases × one Claude call each, about $0.30 per case, so about $0.60, plus one regenerate each to test `<note>`, about $1.20 in total. This is an estimate only, and nothing runs without the Producer's go.

---

## 2. No check is ever a dead end

### What's wrong today

- Problems on a breakdown stop Next. Problems on a frame or clip block rendering (409). There's no override.
- So any flag the editor can't clear by editing is a dead end. Two real cases:
  - **"a montage shot without the main character"** fires on a hand or screen insert ("Theo's hands", "Theo's phone shows…"), because the breakdown didn't list Theo in that shot's `character_ids`.
  - **"the script doesn't end on the brand's end line"** fires at breakdown, but the script's words are locked by then, so there's nothing the editor can do.

### The fix: both prompt-side and check-side

**Prompt side (`breakdown.md`).** List the character in `character_ids` for any insert of their hands, phone, screen or belongings.

**Check side (`check.breakdown`).** A montage shot counts as the hero's when any of these is true:
- it lists a character;
- it shows a screen or product (that's his phone or his desk);
- its action names someone's hands, phone, keys or screen ("Theo's hands").

**Policy: every flag is either "fix" or "advice", and both have a way forward.**

- **Fix** is for things that break generation or one of Reed's hard rules. These still block the step, and each message says exactly what to edit. Regenerate is always offered beside it.
- **Advice** covers things that usually make the video worse but aren't always wrong. It shows with a **Keep anyway** button and never blocks. When an editor keeps one, that's recorded on the row, so it doesn't come back after the next edit unless its text changes.

How it works:
- The check functions keep returning a list of strings. Advice strings start with `Advice: ` (`check.ADVICE`).
- The server blocks only on strings without that prefix. That's Builder-Server's change: one filter in the breakdown Next, storyboard render and clip generate gates, plus a `kept` list on each row.
- The web UI shows advice with Keep anyway. That's the Designer's change.

Sorted:

| Fix (blocks; message says what to edit) | Advice (Keep anyway) |
|---|---|
| a script line is in no shot; a shot's line differs from the script | a montage shot without the hero (after the fix above) |
| a ★ line or required moment has no screen | a clip with more than 3 screens |
| an unknown screen or image id | a quick cut that names nobody |
| a clip's length is outside the model's range, or shorter than its shots | an action that reads like a line ("does not sell") |
| clips don't cover the shots once each | words the image model may refuse ("say it gently") |
| clip prompt shape: the audio line first and last, Summary, Keep, whole-second shots ending at the clip length | characters attached out of order |
| a spoken line isn't in the prompt exactly once | **the script doesn't end on the end line** (at breakdown; it's a fix in Script, Enhance and Variations, before the words lock) |
| more references than the model takes; an image named but not attached; a screen attached but never shown | Quick clip: the shot count differs from the brief |
| a lineless shot doesn't say "No one speaks."; the audio line doesn't match | |
| aspect or resolution written in the prompt | |
| a character in the shot without their sheet (the way forward is to attach it, or make the sheet first, which the sheet warning already links) | |

---

## Who does what, and ETA

| Piece | Who | ETA after go |
|---|---|---|
| Montage check fix + `Advice:` tagging of the advice checks + breakdown.md line (one PR) | Director | same day, about 2 h |
| Gates skip advice; `kept` list per row | Builder-Server | their estimate |
| Keep anyway in the UI | Designer / Builder-Screens | their estimate |
| Variations: `variations.md`, schema, worked example, `check.variations`, eval cases, `run.py --print` (one PR) | Director | about half a day once Builder-Server agrees the schema |
| Variations storage, versions, side-by-side review, regenerate with note | Builder-Server / Builder-Screens | their estimate |

No paid calls in any of this. The paid eval (about $1.20) waits for the Producer.
