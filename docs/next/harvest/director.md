# Harvest: Director (prompts and looks), 30 Oct – 1 Nov

What the prompt side learned, for folding into `rules.md`, the step prompts and brand notes. Each point says where it already lives, or that it still needs a home.

## General craft (every brand)

**Looks**
- A look is its own tells, never a studio name. Name a studio and the model drifts to generic Pixar. Every look file describes what you see, and a look's banned words are repaired in code, free, outside quoted speech (`check.look_words`).
- Worked examples teach the look they're written in. The clip example speaks the video's own look (`_in_look`, #1020), and the reel_watch example describes a reel in plain words (#1035). New examples follow this.
- A format isn't a look. Song carries only its still and clip guides and takes its look from the video (#1031, #1042). Formats are only Song for now (#1047).

**Words on screen and in the mouth**
- Rule 19: quoted speech is never touched, by any step or any repair, capitals included (#1019, #1045).
- Pronunciation goes in the how-it's-said note, never in the quote, and without quote marks, because quotes are speech: `saying fomo as FOH-moh` (#1045).
- Anything that reads like a line gets spoken: a feeling written as inner speech ("can't believe it worked"), or "replies" or "answers" in an action. Write the named emotion and what the face and body do (#1057).

**Pictures**
- More movement: most shots carry a camera move or big action, and they're locked off only where stillness is the point. Edgy gags are played as written, never softened (#1045).
- One shot is one image. "Two quick cuts" in one shot makes a split screen. Quick beats in one place run on as one continuous action (#1057).
- One payoff per montage clip. Payoffs are this video's own, never a stock run (#1045, #1057).
- A time jump opens on a white flash, drawn by the clip itself, because the cut adds no transitions (#1045).

**Brand screens (rule 14, Reed, 30 Oct)**
- A provided screen is attached as itself: UI, logo and layout exact; coin, numbers and chart from the shot. It's invented only when the brand has none for that moment (#1041, #1045).
- A beat's figure is a field, `screen_figure`, so the server can draw it. The figure in the action stays too (#1057, #1059).

**Process**
- Hash every prompt (all steps × looks × video types, plus sheets, samples and schemas) against next before opening a PR. My first script missed reel_watch, and a stale base once showed every step as changed.
- A schema change means regenerating `web/src/api/schema.d.ts` (`npm run api`), or browser-tests goes red.
- Advice checks must count only what they're about (the win-climb hint reads trading screens only, #1055).

**Still open**
- Reed's look re-samples, to judge the looks against his references. They're paid, so they wait for the Producer.
- Starpop study videos: the links need a login, so I haven't checked those looks against them.

## Per brand

**fomo** (for its brand notes, not the global prompts)
- Shown only in a positive light. Losses go on plain, unbranded apps.
- The actual fomo UI is always used. Numbers and coins can be invented, and custom coin screens (SNORE) are fine with fomo branding.
- Loading screens are dark, with the fomo eyes and logo.
- Sold in conversation ("copy good traders", "on FOMO"), never as an obvious ad.
- Write FOMO in capitals in the script. That worked first time on both song end lines. One female voice (project 41) said "Fogo" whatever we tried, so re-voice it.
- Endings: a short yes/no question to the viewer, then the end line. 480p.

**Iron Paws**
- No new learnings this round. The product bag is shown label-to-camera, never with a face. Bed scenes with bodily actions are split, because the model reads them as sexual. Both rules are already in the prompts.

Story logic ("lose X, win X back") stays per story, never site-wide or brand-wide (Reed).
