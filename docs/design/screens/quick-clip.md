# Quick clip

Purpose: one-off clip inside the current brand. The tezu studio pattern, calmer, with brand pieces one click away.
URL: `/b/:brand/clip?character=&screen=&prompt=`. Jobs: `GET /jobs`, `POST /jobs/{id}/cancel`.

## Desktop (1440, ≥ 1024)
```
│ Quick clip · fomo                                                         │
│ ┌ panel 360 ──────────────┐ ┌ workspace ───────────────────────────────┐ │
│ │ Model                   │ │ [History] Ready (8)          List ▤ Grid ▦│ │
│ │ [Seedance 2.5        ▾] │ │ ┌──────────────────────────────────────┐ │ │
│ │  4–30s · up to 1080p    │ │ │[thumb] Rendering 42%  ━━━━━━──────    │ │ │
│ │ Prompt          0/2,000 │ │ │        "Mia taps Buy on…" 8s·480p·9:16 │ │ │
│ │ [textarea 6 rows      ] │ │ │        34 credits       [Cancel]       │ │ │
│ │ Who's in it, what       │ │ ├──────────────────────────────────────┤ │ │
│ │ happens, how the camera │ │ │[thumb] Ready                          │ │ │
│ │ moves.                  │ │ │        "…"  [Download] [Reuse] ⋯      │ │ │
│ │ [✦ Improve prompt]      │ │ ├──────────────────────────────────────┤ │ │
│ │ Brand pieces  2/4       │ │ │[thumb] Failed · credits returned     │ │ │
│ │ [Mia ×][Buy BTC ×][+ ▾] │ │ │        [Try again]                    │ │ │
│ │ Aspect [9:16][1:1][16:9]│ │ └──────────────────────────────────────┘ │ │
│ │ Length  4s ━━●━━━ 30s 8s│ │                                          │ │
│ │ Quality [480p][720p][1080p]                                         │ │
│ │─────────────────────────│ │                                          │ │
│ │[ Generate · 68 credits ]│ │  sticky footer of the panel              │ │
│ │ (reason when disabled)  │ │                                          │ │
│ └─────────────────────────┘ └──────────────────────────────────────────┘ │
```
- **Brand pieces** replaces tezu's "Reference images". The "+" menu has tabs Characters / Places / Props / Screens / Upload, all from this brand. fomo screens marked "Always used for" are pre-added when the prompt mentions that moment, shown with a ★ and removable. Type `@` in the prompt to insert one by name (autocomplete list).
- Model picker: popover listing models from the catalogue, name + one line + "from N credits/s". No provider chips (we only use a few). Switching clamps length/quality and shows a toast if something changed: "Length set to 15s, the most Seedance 2.0 allows."
- **Improve prompt** = our Prompt Assistant: dialog with Idea, Direction chips (Cinematic, Realistic, Funny, Product ad), Shots (1–4), result as editable text with [Use this] — "Nothing generates until you press Generate." After use: ghost [Undo improve] next to the button.
- Generate disabled reasons (first that applies): "Loading a brand piece…", "Describe the clip (8+ characters)", "A clip is already rendering", "Not enough credits — ask Reed".

## Phone (390)
Single column: panel fields, then History below. Generate bar is fixed at the bottom above the tab bar (button full width + reason line), with `--shadow-2`. Model picker and "+ Brand pieces" open as bottom sheets. History rows: thumb 64 wide, status + prompt (2 lines), actions in ⋯.

## States
- Rendering: thin progress bar in `--accent`, text "Rendering 42%"; "Queued" before; "Finishing" at 100%.
- Ready: badge success "Ready"; click → lightbox (video, prompt, Download, Reuse, Send to project ▾).
- Failed: badge danger "Failed · credits returned", one line reason in plain words, [Try again].
- Empty history: "Your first fomo clip starts here." / "Describe a moment, add a brand piece, press Generate." / [Start describing] (focuses prompt).
