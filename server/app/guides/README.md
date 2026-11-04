# Guides: one place for every format and every style

Every video is a **format** (how the script reads: its structure, pacing, beats and sound) in a
**style** (how it looks and how the camera moves), for a **brand**. Each format and each style is
one file here, and the site reads nothing else for them. Edit a file and the next video uses it,
word for word.

```
craft.md                         story and engagement, for every video
formats/<id>/guide.md            one format (dialogue, song, narrated, zack-d, presenter)
formats/<id>/examples/           its worked examples
styles/<id>/guide.md             one style (house, disney-pixar, skeleton, ...)
styles/<id>/lanes/<lane>.md      a lane: one way of making that style
styles/<id>/examples/            its worked examples
```

Who reads what: the director and every writing step (the treatment, the plan, the breakdown,
the storyboard, the clip prompts, the stills review, the watch of the cut) get `craft.md`, then
the video's format guide, then its style guide (with its lane), then up to three of their
studied examples. Where the style and anything before it differ on how a picture looks, the
style wins.

## A guide file

It starts with a few `key: value` lines, then a blank line, then sections. Each section starts
with `## ` and a name.

```
name: Watercolor
order: 8
on: no
image_model: auto
blurb: One line for the style's card.

## Stills
- Guidance for the pictures...
```

- `name` is what people see; `order` is where it sits in the lists; `on: yes` makes it
  available from the start (for a style, the owner's switch on the Styles page decides after
  that); `blurb` is the one line on its card.
- A style also has `image_model` (leave it `auto`). A format also has `engine`: `story`,
  `song` or `narrated`, the machinery that makes it (a song is timed to its track, a narrated
  video to its narration, a story to its lines). A narrated format may also have `host: yes`:
  the site then makes a host who says the narration on camera (one still on green, lip-synced
  in pieces) and lays them over the B-roll in the final cut (Presenter).
- New video's cards (optional): `card` is the short line under the name ("Handmade clay"); a
  style's `broll` names its B-roll look ("Clay props"), shown as "B-roll: clay props" and in
  Change B-roll look. Without `card`, the card shows the blurb. `hidden: yes` keeps a style
  out of every list (Reed, 3 Nov, on Paper, Watercolor, Wool crochet and Anime comic: "do not
  build it").
- Notes for people go in `<!-- ... -->` before the first section; the model never sees them.

Most sections are guidance: write them like advice to a director, and every writing step reads
them. A few names mean something to the site:

| Section | What the site does with it |
|---|---|
| `sheet_look`, `place_look`, `still_look`, `clip_style`, `fit_look` | The look's own words, put into the step prompts where they say `{{sheet_look}}` and so on. Every style needs all five. |
| `Script` | Also reaches the script writers (a new draft, Enhance, Variations). |
| `Clips` | Also reaches Improve. |
| `lanes` | The plan reads it to pick this video's lane. |
| `banned` | One `word → replacement` a line, repaired in picture prompts (never sent as guidance). |
| `fixes` | The fix the site offers for each failed check (`refused:`, `face:`, `outfit:`, `product:`). |
| `sample` | The person in the style's sample still. |

A `## ` line inside a ``` block is part of that block, not a new section.

## Add a format

1. Make `formats/<id>/guide.md` (the id is lower-case with dashes, like `zack-d`).
2. Give it `name`, `order`, `on`, `engine` and `blurb`, then its sections: how the script reads,
   its structure, its pacing and its sound.
3. It shows up in the format list (`GET /formats`) at once.

## Add a style

1. Make `styles/<id>/guide.md` with `name`, `order`, `on: no`, `image_model: auto` and `blurb`.
2. Write the five look sections (`sheet_look` ... `fit_look`), then any guidance: how it looks,
   how the camera moves, its shots and transitions. Add `banned`, `fixes` and `sample` if it
   needs them.
3. It appears on the Styles page, off; make its sample there and switch it on.

## Add a lane

A lane is one way of making a style (Paper's Origami, Claymation's Goofy).

1. Make `styles/<style>/lanes/<style>-<lane>.md` with `name`, `order` (just after its style's,
   like `7.4`) and `blurb`.
2. Write only the sections that differ from the style. Every section it leaves out comes from
   the style's `guide.md`; a section it writes replaces the style's one of the same name. An
   empty section means the lane has none of it (the Skeleton and Claymation lanes have an empty
   `fixes`).
3. Add a line for it to the style's `lanes` section, so the plan can pick it.

## Add an example

Put a studied example in `formats/<id>/examples/<name>/study.md` or
`styles/<id>/examples/<name>/study.md` (`server/scripts/study_example.py` writes these; see
`EXAMPLES.md` here, once it lands). Every
writing step gets up to three of them, the format's first. The `.json` files in
`formats/dialogue/examples/` are the step prompts' worked examples (the fomo shorts); they reach
only the format they sit in.
