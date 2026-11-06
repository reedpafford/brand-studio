name: Anime comic
order: 6
on: no
hidden: yes
image_model: auto
video_model: gemini-omni-1.2
blurb: Original cel-shaded anime: clean ink lines, two-tone shading, strong key poses and impact frames.

<!-- Reed's anime-comic skill (docs/next/skills/anime-comic.md, #1097; first from Starpop's anime-comic-ads, docs/research/starpop-2026-10-28, rule 20): one original graphic language held across the ad. We pick cel-shaded anime; inked comic or manga screentone could be their own entries. -->
<!-- Moved 2 Nov from server/app/prompts/styles/anime-comic.md and prompts/skills/anime-comic.md into one place. -->
<!-- Reed's skill file (was prompts/skills/anime-comic.md), its chat front matter: name: anime-comic-animation; description: "Activate when the user wants an anime, manga, comic-book, cel-shaded, or graphic-panel animated ad." -->

## sheet_look
Original cel-shaded anime illustration: clean, even ink line weight, two-tone cel shading with one shadow tone, flat bright colour fills, a readable silhouette and simple facial proportions with large expressive eyes. An original character: never one that resembles an existing anime, manga or comic character, costume, franchise symbol or a named artist's exact style. The line weight, the one shadow tone, the palette and the texture are set once here and held in every shot. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit with simple, bold shapes, identical in every view, and one silhouette-defining item that reads at a glance.

## place_look
Original cel-shaded anime background art: clean ink lines, flat colour fills with one shadow tone, soft painted sky gradients, a clear readable layout with the depth carried by colour and value.

## still_look
The Anime comic look, unless the brand block says otherwise: "Original cel-shaded anime frame: clean, even ink lines, two-tone cel shading, flat bright colour, painted background art, a strong key pose and a readable silhouette. Faces and builds come from the character sheets, and outfits too unless this video gives its own. Expressions are big and graphic, readable with the sound off."

## clip_style
Original cel-shaded anime animation, clean ink lines and two-tone shading, pose-to-pose with purposeful holds and snappy impact frames

## fit_look
an original cel-shaded anime look with clean ink lines

## Stills
- Every shot is a strong key pose. Speed lines, halftone, an impact frame or an ink border round the whole frame only when they sell the moment (the win, the reveal), never as decoration. One full frame per shot: never several panels, a grid or a split frame in one image. No speech balloons or captions: words are added in editing. Never a composition copied from a known anime, manga or comic frame.
- Prioritise silhouette and expression over fine detail. The product keeps its real shape and label, drawn in the same line and shading.

## Clips
- Animate pose to pose: hold the key pose, snap to the next on the beat, with a restrained camera move. A reveal or a power-up can land on an impact frame.

## Breakdown
- Strong key poses carry it: plan each shot around one pose that reads at a glance. Devices this look tells well, when the story has one: a transformation, a dramatic reveal, a versus (shot against shot, or both rivals in one scene), a power-up that shows how the product works, a hero talking to the viewer, or an explainer told one full-frame shot at a time, with comic-panel transitions between them.

## sample
A determined young adult with spiky black hair and bright eyes, in one plain navy jacket, in a strong key pose.

## How to make anime and comic animation ads
Choose one original graphic language and hold it across the ad.

Treat genre references as broad craft direction, never as permission to copy a protected character, costume, franchise, or exact artist style.

## Workflow
1. Resolve the product, audience, angle, proof, CTA, runtime, and platform.

2. Choose one visual system: cel-shaded anime, inked comic, manga screentone, graphic novel, or pop comic.

3. Design an original hero with locked silhouette, facial proportions, palette, outfit, line weight, and shading method.

4. Choose the narrative device: transformation, dramatic reveal, versus comparison, power-up mechanism, talking hero, or panel-by-panel explainer.

5. Storyboard strong key poses before generating motion.

6. Generate consistent start frames with the same character and product references.

7. Animate pose-to-pose with purposeful holds, impact frames, panel transitions, and restrained camera movement.

8. Add exact speech balloons, captions, and typography in editing.

## Visual rules
- define line weight, shadow count, palette, and texture once

- prioritize readable silhouettes and expressions over micro-detail

- use speed lines, halftone, impact frames, or panel borders only when they reinforce the shot

- preserve the supplied product geometry and label

- avoid protected characters, costumes, franchise symbols, and copied compositions

## Quality checks
- Does each shot have a strong key pose?

- Does the character remain original and consistent?

- Are graphic effects supporting the product story?

- Is exact text handled in post rather than entrusted to image generation?
