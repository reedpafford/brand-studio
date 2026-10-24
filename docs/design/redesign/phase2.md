# Redesign, phase 2: visual direction

Three directions for Reed to pick from. Each one is shown on the same three screens, on phone (390) and desktop (1440):
- **Videos home**
- **a video at the Clips step**
- **Cast & places**

All three use the approved phase-1 structure (#170). They differ only in how it looks.

Boards: `phase2/direction-A.png`, `phase2/direction-B.png`, `phase2/direction-C.png`. Every screen at full size is in `phase2/screens/` (`<direction>-<screen>-<width>.jpg`).

How they were made:
- Static HTML mockups, screenshotted with Playwright. No paid calls.
- The pictures are frames from the house-style board (`docs/house-style/board.jpg`) and the brand's real assets, so each card shows the kind of image the app really makes.
- I compared against tezu (`docs/tezu/shots`, `TEZU-MAP.md`):
  - tezu's dark studio puts the media first.
  - It has a single bright action per panel.
  - Its cost sits inside the button.
  - Its type is big and bold.

## A · Cutting room
*Today's calm warm-paper studio, sharpened: real pictures on every card, one teal action per screen, and the brand's colour as the thread through the app.*

- **Palette:**
  - paper #F5F3EE · card #FFFFFF · ink #1C1B19 · muted #67635B
  - teal #0E6F64 (soft #DDEEEA)
  - approved #1F7A3E · brand colour as the top stripe and dot
- **Type:** Inter throughout (titles 28/22/19, body 15, 16 on phones). Courier Prime for scripts and prompts.
- **Good:** closest to what's built, so the quickest and safest to ship. It's light and readable, and a dark mode already exists.
- **Watch out:** the least "wow" next to tezu. The pictures sit inside frames rather than leading.

## B · Screening room (recommended)
*A dark, cinematic studio like tezu: frames and takes lead edge to edge, titles sit on the picture, and golden-hour amber marks the one thing to press.*

- **Palette:**
  - night #0B0B0D · panel #151517 · raised #1E1E21
  - text #F3F2EF · muted #A3A1A9
  - amber #F4A940 (dark text on it) · approved #5BD08A
  - brand colour on the dot
- **Type:** Manrope for titles (32/22/19, heavy and tight), Inter for text. Courier Prime for scripts and prompts.
- **Layout:**
  - Desktop has a side rail: the brand's four sections, then a separate "Studio" group (Approvals, Team) for Reed.
  - Phone has the four bottom tabs and a fixed action bar.
- **Good:** reaches and beats tezu's level. Video and stills look their best on dark, and the work leads, not the forms.
- **Watch out:**
  - Long forms (brief, brand) feel heavier on dark.
  - Contrast needs care, especially muted text and the amber disabled state.
  - We still owe a light mode.

## C · Brand-led editorial
*Clean white pages where each brand dresses the app: its colour leads the buttons and a brand band, and serif titles make it feel like the brand's own studio.*

- **Palette:** white #FFFFFF · soft #F4F4F1 · ink #121211 · muted #5F5E59 · the brand's colour as the accent (Iron Paws #1E5B44, fomo #0E7A3C) · approved #1E6B3A.
- **Type:** Fraunces serif titles (34/21), Inter text. Round buttons and hairlines instead of shadows.
- **Good:** every brand feels like its own studio. Premium and editorial.
- **Watch out:**
  - Some brand colours won't pass contrast with white text, so they need a darker variant.
  - Furthest from tezu, and the serif may feel less like a tool.

## Recommendation: B, Screening room (picked by Reed, 2026-10-24)
- **Why:** Reed asked for tezu's level or better, and this app is mostly about looking at frames and takes. B gives the work the most room and the most impact, and keeps one obvious amber action per screen.
- **What it keeps from A:** the warm neutrals become B's **light mode**, built in phase 3 from the same tokens, for anyone who prefers it.
- **What it keeps from C:** the brand still shows (the brand dot, and the brand's colour on its own pages) without fighting the amber action colour.

## After Reed picks
Phase 3 turns the chosen direction into the design system:
- spacing, type, colour, radius and shadow tokens in the Tailwind theme, in dark and light
- every state (empty, loading, error, success)
- 44px tap targets, motion that respects reduced-motion
- one spec per screen for Builder-Screens
