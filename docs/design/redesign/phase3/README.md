# Redesign, phase 3: the Screening room design system

This is the build spec for the redesign Reed approved:
- **Structure:** phase 1, #170.
- **Look:** direction B, Screening room, #173.

Builder-Screens builds from this folder. Nothing ships until spacing, alignment, wording and icons match it.

| File | What it is |
|---|---|
| `contrast.py` | WCAG AA check of every colour pair in both modes. Run it after any colour change: `python3 contrast.py`. It must show 0 FAIL. |
| `component-sheet.png` | Every shared part, as built from `tokens.css`. |
| `clips-states.png` | One screen (a video at the Clips step) in all of its states, on phone and desktop. |
| `screens/*.md` | One spec per screen group: layout at 390 and desktop, exact wording, icons, and the empty, loading, error and success states. |

## 1. Rules for every screen
1. **One amber button per screen.** It's the next step, and it sits in the same place every time:
   - Desktop: top right of the work area.
   - Phone: the action bar fixed above the bottom tabs.

   Everything else is secondary (raised panel), ghost (text only) or danger.
2. **Paid buttons say the price inside the button:** "Make the takes · 8 credits". Past a limit, editors never see "Ask Reed" or "Waiting for Reed" (Reed, 2026-10-26): the button is disabled with the reason under it, "That's more than this video's budget." on a library version, or "That's more than this week's 145 free credits. It resets on Monday." on their own script or Quick clips. Reed sees the plain button past a budget; his press is the approval. Prices are whole credits; round up, so 67.5 shows as 68.
   - **When the price can vary** (a look's sheet, which may get one automatic redo after its fit check), the button shows the most it can cost: "Make a look · up to 4 credits". A meta line under it says the usual price: "Usually 2. Anything not used comes back." Limits are checked against the "up to" price. Afterwards, notes and Usage show what it really cost ("Made 3 looks · 7 credits").
3. **A disabled button always says why,** in muted text on the line under it: "Approve every clip first (2 left)".
4. **Status is always in words,** with colour as a second signal (badges, see the sheet). Never a coloured dot alone.
5. **Editors never see dollars.** Dollars appear only on Approvals, for Reed.
6. **44px minimum for every control on phones,** with 8px between controls. On desktop, secondary controls may be 36px (`dense`); amber buttons are always 44px.
7. **No sideways scroll at 390.** The one exception is a chip or filter row that scrolls inside itself, with a fade at its right edge.
8. **Pictures lead.** Video, frame, take and character cards are media-first:
   - The title sits on the picture, over the `--media-shade` gradient.
   - The status badge is top left.
   - A play button appears only on things that play.
9. **Plain words.** Use the wording in the specs exactly. Don't show internal ids, raw prompts with `[Image1]`, version numbers ("v3"), or model jargon outside the model picker.
10. **Every screen has four states,** and each spec lists them:
    - **Empty:** what this is, plus one button.
    - **Loading:** a skeleton in the final layout, with a count-up after 1s ("Writing prompts… 12 s").
    - **Error:** what happened, what was charged (usually nothing), and what to do, with a button.
    - **Success:** a toast, plus the next step lighting up.
11. **Approve all** (Reed, 2026-10-26): every list where items are approved one by one gets **Approve all**, with the same behaviour everywhere (`workflow-v2/video-flow.md`, Approve all). It's secondary, with `Check`, and placed before the step's amber button. It reads **Approve 8** when not every item is ready. It approves only ready items and lists the skipped ones as "{label}: {reason}", separated by " · ". The toast has **Undo** (8 s), which takes back exactly those. Lists: Storyboard frames, Clips, Assets looks, Variations, and any later list with a per-item Approve.

## 2. Tokens in use
- **Colour:** only the token colours exist (`--color-*: initial` in the theme). Use the classes: `bg-surface`, `bg-surface-2`, `text-muted`, `border-border`, `bg-accent text-on-accent`, `bg-success-soft text-success`, and so on. No hex values in components.
- **Space:** Tailwind's 4px unit, using these steps only: 1, 2, 3, 4, 5, 6, 8, 10, 12, 16. That means `p-4`, `gap-3`, `mt-8`; not `p-7` or `[13px]`.
  - Card padding: 16 on phone, 20 on desktop.
  - Page gutters: 16 on phone, 32 on desktop.
  - Gap between cards: 12 on phone, 16 on desktop.
  - Section gap: 32.
- **Type roles** (use these classes, not raw sizes):

  | Role | Font | Size / line | Weight | Use |
  |---|---|---|---|---|
  | page | Manrope | 32/38 (26/32 phone) | 800, tracking −0.02em | Page and video titles |
  | headline | Manrope | 24/30 | 750 | Empty-state headlines, dialog titles |
  | section | Manrope | 20/26 | 700 | Section titles ("In progress", "Clips") |
  | card | Manrope | 17/22 | 700 | Card titles, on pictures too |
  | body | Inter | 15/22 (16/24 phone) | 400 | Text, controls |
  | label | Inter | 13/18 | 500 | Field labels |
  | meta | Inter | 13/18 | 400, muted | Helper text, timestamps, counts |
  | eyebrow | Inter | 12/16 | 700, caps, +0.12em | Small group labels ("IN PROGRESS") |
  | caption | Inter | 12/16 | 600 | Badges, timecodes |
  | script | Courier Prime | 14/22 | 400 | Scripts, clip and frame prompts |

  Numbers (credits, seconds, counts) use `tabular-nums`.
- **Radii:** 6 badge · 10 button, field, small media · 14 card, media card · 20 sheet, dialog · full for pills and avatars.
- **Elevation:**
  - Cards use `shadow-card`, a hairline edge in dark mode.
  - Menus and toasts use `shadow-raised`.
  - Sheets and dialogs use `shadow-overlay` over `bg-scrim`.
- **Motion:**

  | Token | Duration | Used for |
  |---|---|---|
  | `--dur-instant` | 80ms | press (scale 0.98) |
  | `--dur-fast` | 140ms | hover, focus |
  | `--dur` | 220ms | tab, step and card changes (crossfade plus 8px rise) |
  | `--dur-slow` | 320ms | sheets and panels in |
  | `--dur-exit` | 160ms | sheets and panels out |

  - Only `transform` and `opacity` animate.
  - Lists stagger 30ms per item, at most 8 items.
  - With reduced motion, durations become 1ms and nothing slides; state still changes.
- **Theme:** dark by default. The account menu offers **Theme: Dark / Light / Match my device**, setting `data-theme` to `dark`, `light` or `system`. The choice is kept in localStorage (`bs-theme`), as today.

## 3. Icons: Lucide only
Use `lucide-react` (one new web dependency). Icons are 20px, stroke 1.75, and `currentColor`; 16px inside small buttons and badges. Icons beside text are `aria-hidden`. Icon-only buttons need an `aria-label`, plus a tooltip on desktop.

| Meaning | Icon | Meaning | Icon |
|---|---|---|---|
| Videos | `Clapperboard` | Script | `FileText` |
| Quick clip | `Zap` | Play | `Play` |
| Cast & places | `Users` | Claude writes / suggests | `Sparkles` |
| Brand | `Palette` | Waiting / time left | `Clock` |
| Approvals | `Bell` | Problem / needs action | `TriangleAlert` |
| Team | `UserPlus` | Error | `CircleAlert` |
| New / add | `Plus` | Search | `Search` |
| Done / approved | `Check` | Upload | `Upload` |
| Close / remove | `X` | Download | `Download` |
| Open list | `ChevronDown` | Redo | `RotateCcw` |
| Next / go into | `ChevronRight` | Edit | `Pencil` |
| Back | `ChevronLeft` | Delete | `Trash2` |
| Busy | `LoaderCircle` (spins) | More actions | `Ellipsis` |
| Product | `Package` | App screen | `Smartphone` |
| Place | `MapPin` | Prop | `Box` |
| Undo | `Undo2` | Info | `Info` |
| Theme | `Sun` / `Moon` | Sign out | `LogOut` |
| Storyboard, picture | `Image` | Clips, takes | `Film` |
| Copy link | `Copy` | Dead link | `Link2Off` |
| Archive, deleted and archived | `Archive` | Release a version | `Undo2` |
| Change it (plain-English note) | `Wand2` | Put the right cast in each shot | `Users` |

Emoji are never icons. Today's ✓, ★, ▸ and ✦ glyphs become `Check`, `Smartphone` (brand screen mark), `ChevronRight` and `Sparkles`.

## 4. Screens
| Spec | Covers |
|---|---|
| `screens/shell.md` | Top bar, side rail, phone tabs and action bar, brand switcher, account menu, toasts, sheets and dialogs, page frame |
| `screens/auth.md` | Sign in, first-time setup, join from an invite |
| `screens/videos.md` | Videos home (in progress, finished, Reed's requests banner) |
| `screens/new-video.md` | New video (the brief form), Edit brief |
| `screens/video.md` | A video: header, step picker, Script panel, and the six steps (Brief, Script, Shots, Storyboard, Clips, Final video) |
| `screens/quick-clip.md` | Quick clip and its history |
| `screens/cast.md` | Cast & places list, character / place / prop page, house-style sheet |
| `screens/brand.md` | Brand: Look, Products, App screens |
| `screens/studio.md` | Approvals and Team (Reed only) |

## 5. Build
All 14 build PRs have landed (#175–#221 and the workflow-v2 screens). Keep to these specs when changing a screen.
