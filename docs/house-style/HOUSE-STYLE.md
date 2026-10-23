# House style: @nateassets animated reels

What this is: the default look, sound and storytelling for every Brand Studio video, taken from the 12 most-viewed animated reels on Instagram account **@nateassets** (2.7M–16.4M views each). Every number here was measured from those reels: cut detection checked by eye, frame strips, faster-whisper transcripts cross-checked against the burned-in captions, and pixel colour statistics. Per-reel shot-by-shot breakdowns are in `docs/references/nateassets/<reel_id>/`. The 12th reel, DehudnaAmce, is `docs/references/fomo-DehudnaAmce/`. The style board is `board.jpg` (next to this file).

**Copy the craft, not the content.** Never copy their captions, dialogue, characters (Nate, Mom, Dad), real brand logos (Ferrari, LV, Nike, Apple) or the creator's real-life footage. Make new characters and stories in the same style.

---

## Visual style line (first line of every image/video prompt)

> Stylised 3D animated feature-film look (Pixar/Disney-like CG). Characters have slightly enlarged heads (about 6 heads tall), big glossy round eyes with one sharp catchlight, thick expressive brows, small noses and soft subsurface skin. Wardrobe is simple, clean and real-world, with fine cloth and prop detail. Lighting is motivated and cinematic: warm amber practicals or golden-hour sun against cool blue shadows, deep but not crushed blacks, no blown highlights. The frame is mostly locked off at eye level with a shallow depth of field and creamy background blur. Expressions are big and readable with the sound off.

A short version for tight prompt budgets: *"Pixar-style 3D animation, big glossy eyes, soft subsurface skin, warm amber key against cool blue shadows, shallow depth of field, locked-off cinematic framing, big readable expressions."*

All reels are vertical 9:16. Set the aspect ratio as the generation setting, never in the prompt text (our prompt checks reject ratios in prompts).

---

## The 12 reference reels

| Reel | Views (reported) | Posted | Length | Shots | Median shot | Words/s | Story family |
|---|---|---|---|---|---|---|---|
| DcP_aC_AoQz | 16.4M | 2026-08-20 | 60.0 s | 57 | 0.51 s | 4.70 | "Mom said I'd fail" |
| DeV-XBfgvTC | 8.2M | 2026-10-11 | 43.0 s | 41 | 0.42 s | 4.19 | Ex chose money |
| DeukYhBBTKE | 7.6M | 2026-10-20 | 44.0 s | 45 | 0.70 s | 4.25 | Status-gap underdog |
| DbzbABRAb-G | 6.2M | 2026-08-09 | 59.8 s | 42 | 0.45 s | 3.48 | "Mom said I'd fail" |
| DeM4aSbg1OI | 6.2M | 2026-10-07 | 39.6 s | 40 | 0.74 s | 5.42 | Ex chose money |
| DdvU49JgfEw | 5.7M | 2026-09-26 | 56.0 s | 48 | 0.66 s | 5.73 | "Mom said we'd fail" (collab) |
| Ddj8JCsA6Zr | 5.5M | 2026-09-21 | 56.3 s | 42 | 0.64 s | 5.09 | "Mom said I'd fail" |
| Dd5zmcgAj0M | 5.5M | 2026-09-30 | 56.0 s | 64 | 0.40 s | 5.37 | "Mom said I'd fail" |
| DehudnaAmce | 4M | 2026-10-15 | 45.0 s | 50 | 0.40 s | 2.82 | Ex chose money |
| DdsEQhNAyl4 | 3.6M | 2026-09-24 | 56.0 s | 53 | 0.50 s | 5.02 | "Daddy said I'd fail" |
| Ddcye3FAaZE | 2.8M | 2026-09-19 | 71.4 s | 59 | 0.70 s | 4.92 | "Stepmom said I'd fail" |
| Db35MX-A_mA | 2.7M | 2026-08-10 | 89.0 s | 95 | 0.50 s | 4.72 | "Dad said I'd fail" |

All 12 are 3D animated; none were skipped. Every reel ends with a 1.45–3.7 s live-action "real me" tag.

---

## 1. What makes them work (the director's summary)

1. **They start at the fight, not before it.** The first word is spoken at **0.0–0.35 s** in every reel. The opening line is an accusation or a rejection ("Nate! Where is all your money?", "HELL NO!", "You sold all my stuff?"). Median hook is **5.4 s**, with the stakes stated as a number ($2,000, $200, 30 days, one week).
2. **One underdog, one doubter, one promise.** A doubter (parent, ex, rich rival) mocks the hero. The hero answers with a short dare ("Then prove it." / "Just watch." / "One week."). The rest of the reel pays off that promise.
3. **The middle is a wordless montage that shows proof.** In 11 of 12 reels the grind is told with no dialogue: hands, screens, packing, day/night flips, and the same pose in an ever-bigger room. Montage shots have a median of **0.42 s** (pooled over 216 montage shots; per-reel 0.16–0.83 s).
4. **There is a low point before the win.** A night scene, lit cold and blue, with the hero alone ("I can't let her down"), then a ding: the first order or sale lands on a phone screen in close-up.
5. **The reversal mirrors the opening.** The same doubter, often in the same place, now sees the hero's success. The hero gets a short, quotable, slightly smug line ("You were busy arguing. I was busy getting paid." / "Sorry, I'm fully booked." / "No. We did.").
6. **A comic button after the payoff.** A whip-blur into the doubter's screaming extreme close-up ("WHAT?!", "more inventory?") lands in the last 1–2 s of the CG.
7. **A "true story" bridge at the end.** A hard cut to about 2 s (1.45–3.7 s) of real handheld footage. For our brands, this slot is where the **real brand element** goes (fomo's real app screens, the real Iron Paws bag), never the creator's life.
8. **It plays on mute.** Faces are huge and expressive, every line is captioned word by word, and the story shows in props (wallet, ring box, boxes of stock, supercar).

---

## 2. Character design

Measured on close-ups with a grid overlay (DehudnaAmce 0.95 s, DcP_aC_AoQz 0.66 s, full-figure shots in DehudnaAmce and DeukYhBBTKE).

| Feature | Measurement / rule |
|---|---|
| Body | About **6–6.5 heads tall** (crown to chin; a real teen is about 7). Slim, normal limbs; hands slightly large and soft. Adults are caricatured by type: the rich rival or dad has a huge square jaw and broad chest; the mom is slim with a bob. |
| Head / face shape | Soft oval for the young hero; a short chin and full cheeks. The rival or dad has an oversized, block-like jaw (a "villain" read at a glance). |
| Eyes | Big and round: **each eye about 23 % of face width** (hero) and **25–28 %** (women). The gap between the eyes is about 0.9 of an eye width. The iris is about **60 % of eye width**, warm brown for the hero and bright blue for love interests. One sharp white catchlight, upper side. In shock the white shows all round the iris. |
| Eye line | At about 51 % of head height (crown to chin), so eyes sit mid-head as in real anatomy. The stylisation comes from size, not placement. |
| Brows | Thick, dark and graphic, the main acting tool. Worried brows tilt up in the middle; anger is a hard V low over the eyes. |
| Nose / mouth | Small, simple nose with a soft rounded tip. The mouth is small at rest and opens **very** wide on shouts (ECU screams fill 40 % of frame height). Clean, slightly oversized white teeth. |
| Skin | Warm and smooth, with soft subsurface glow (ears and nose light up when backlit) and almost no pores. Hero's daylight cheek **#9F5C46**, warm interior (woman) **#AF6343**, night phone-lit **#6C5C63**. |
| Hair | Simple sculpted clumps with fine strand detail at the edges. The hero has dark curly hair under a cap; women have long glossy waves or a neat bob. |
| Wardrobe | One fixed outfit per character, repeated in every scene (that is what keeps them recognisable). Hero: oversized plain tee with a small chest logo, thin silver chain, stud earring, dark joggers, white sneakers, cap worn backwards. After the time jump the *same* character is upgraded (black suit or knit tee, heavier chain, glasses, the cap now forward) so the success reads instantly. |
| Consistency | Always keep the same face, hair, outfit and logo. Small model drift does occur in the source (DeukYhBBTKE's rival changes build). Avoid it: attach the character sheet to every shot. |

For brand videos: design new characters to these proportions. Give each one a single silhouette-defining item (the cap, the bob, the jaw) and a fixed colour pairing (hero: white plus navy).

---

## 3. Rendering look

- **Materials:** feature-animation CG. Skin is matte-soft with subsurface glow; eyes are wet and glossy; fabric shows fine weave (tees, knit, suiting); props are photoreal and specular (car paint, rims, phone glass, poly mailers, cardboard).
- **Sharpness:** crisp on faces and props. The background drops off quickly (shallow depth of field) into creamy blur and big round bokeh at night. Real motion blur on fast moves and whips.
- **Texture:** clean, with no film grain and no outlines; slight bloom on bright practicals and windows.
- **Density:** sets are dense and specific: walls of stock, shelves, boxes, framed posters, palm trees, city skylines. Empty rooms only appear at the low point.

---

## 4. Lighting

Every scene has a clear, motivated source. Use these six set-ups (they cover nearly every shot in the 12 reels):

| Set-up | When | Key / fill / rim | Board example |
|---|---|---|---|
| **Warm day interior** | Home confrontations | Soft window key from camera side; warm bounce fill; walls stay cool grey-blue | Mom CU (DcP_aC_AoQz 0.7 s) |
| **Night screen-glow** | The grind, the low point | Cool blue phone or laptop light from below-front as the key; the room near black; often a **warm tungsten doorway behind** (two-tone) | DcP_aC_AoQz 22 s; DbzbABRAb-G 24 s |
| **Golden hour / sunrise** | Turning points, "trying", romance, proposals | Low sun backlight with a strong rim on hair and shoulders; lens flare and bloom | DcP_aC_AoQz 25.3 s; Ddcye3FAaZE 18.9 s; DeV-XBfgvTC 0.5 s |
| **High sun exterior** | Status scenes: villas, supercars | Hard sun from back-side, blue-sky fill, warm bounce from the ground | DeukYhBBTKE 3 s |
| **Blue hour / city night** | Confrontations and reveals after the time jump | Cool ambient light, warm street and car practicals, city bokeh | DeV-XBfgvTC 26.5 s; DeM4aSbg1OI 27.9 s |
| **Warehouse / showroom** | Scale-up | Overhead cool-white strips or hexagon LED, symmetrical, glossy reflections | DehudnaAmce 23.6 s |

Flashbacks are overexposed warm pink-peach with bloom. Contrast is cinematic but kept in range: **12.8 % of pixels are near-black (luma < 16), only 0.2 % are clipped white.**

---

## 5. Colour palette and grade

Measured over the CG portion of all 12 reels (2 frames per second):

- **Exposure:** low-key. Median luma is **71/255** (mean 87); 5th percentile 6, 95th percentile 205.
- **Saturation:** moderate. The mean is **40 %**; only **21 %** of pixels are strongly saturated, so colour comes from accents against a neutral base.
- **Temperature:** warm-led. **40 % of pixels are warm hues against 18 % cool**, giving a gentle orange-and-teal split (warm skin and practicals, cool shadows and night).
- **Base palette** (median-cut, dark to light; % of pixels):
  `#07070D` 9.6 · `#13131A` 10.3 · `#192131` 5.3 · `#312A2C` 11.9 · `#5E382E` 11.6 · `#5B595F` 7.9 · `#836351` 8.0 · `#AA674E` 7.0 · `#968580` 8.5 · `#AAA7A9` 6.3 · `#D7AA8F` 5.4 · `#E7DFD8` 8.1
- **Accents** (median colour of saturated pixels per hue family; % of accent pixels):
  skin / red-orange `#885637` 58 % · warm red shadow `#97463A` 19 % · navy / cap blue `#2E5181` 11 % · steel blue `#29689D` 4 % · tan `#8C6B38` 3 % · crimson (cars, ring box) `#AF2F34` 3 % · gold `#8F8234` 1 %
- **Rule of thumb:** neutral rooms (beige, grey, off-white `#E7DFD8`), dark navy shadows (`#192131`), warm skin, plus **one saturated hero object per scene** (red car, red ring box, pink stock, purple hypercar). Purple and magenta LED light appears only in the live-action tags and for "wealth" objects.

---

## 6. Lens and camera

Measured over 537 CG shots:

- **Framing mix:** close-ups and medium close-ups **30 %**; extreme close-ups **8 %** (eyes, a screaming mouth, a phone screen, a wheel); wides and full shots **24 %**; the rest mediums and two-shots.
- **Focal length feel:** close-ups are normal-to-long (about 50–85 mm), with flattering faces and a blurred background. Wides are slightly wide (about 24–35 mm) and often symmetrical (warehouse aisle, villa, Eiffel Tower).
- **Angles:** mostly eye level. Slightly low for confident or arrival moments, slightly high for the hero at his low point. Arguments are a **profile two-shot, nose to nose**.
- **Movement:** **60 % of CG shots are locked off.** About 10 % use a push-in, snap zoom or crash zoom, always on a feeling (realisation, shock, smugness). Reveals use one continuous follow or arc (up to 8–10 s, e.g. DcP_aC_AoQz 49–57 s, Db35MX-A_mA 14–25 s). There is no handheld in the CG; handheld is only used for the real-life tag.
- **Objects to lens:** wallets, ring boxes and phones are thrust at the camera for emphasis, and thrown objects (bags, boxes, shirts) serve as wipes.

---

## 7. Acting and expression

- **Big and readable**, like a sitcom on mute: saucer eyes, a slow jaw drop, gritted-teeth fury, full-body jumps, a head buried in the arms.
- **The hero underplays at the payoff**: a small smirk, a slow blink, walking off mid-sentence. Doubters overplay (screams, begging brows), and their reaction is the punchline.
- **Reaction timing:** the reaction shot comes **immediately** (0.1–0.5 s inserts, often several in a row: rival, priest, crowd). Every big line gets a cut to the listener's face.
- **Emotional beats get time:** the low-point close-up holds for 3–5 s with a slow push-in. It is the only place the pace slows.

---

## 8. Editing rhythm

Measured over all 636 shots (CG plus tags):

- **Shot length:** median **0.55 s** (CG only **0.67 s**). 10th percentile 0.14 s, 25th 0.26 s, 75th 1.26 s, 90th 2.56 s. **46 % of shots are under 0.5 s**; only **8 % run over 3 s** (dialogue two-shots and continuous reveal moves).
- **Rate:** about **1 cut per second** (median 0.95 cuts/s). A typical reel is 40–64 shots in 40–60 s (median 49 shots, 56 s).
- **Hook:** median **5.4 s** (range 3.5–10.6 s), packing 5–7 shots, opening on the conflict line at 0 s.
- **Montage devices:**
  - Wordless macro "process" inserts (typing, packing, spraying).
  - Matched before/after frames (dirty wheel, then clean wheel).
  - **Same pose, bigger world** match cuts (the background swaps from bedroom to stockroom to warehouse).
  - Day/night flicker on a locked-off frame.
  - Fast motion with other characters at normal speed.
  - 0.08 s white or blue flash frames.
- **Transitions:**
  - **Whip-blur cuts** (in nearly every scene change; median 5.5 per reel).
  - Snap or crash zooms into a reaction.
  - **White flash** into a time-jump card ("2 YEARS LATER…", "THREE YEARS LATER") on a hero object.
  - Cut to black before the tag.
- **Ending:** payoff line, then a comic button (scream ECU), then a hard cut to a **2.05 s** real tag (median; range 1.45–3.7 s) with 0.1–0.4 s handheld cuts.

---

## 9. Sound

- **Dialogue-led, no narrator.** Characters speak to each other on screen in short 1–5 word lines, fired back and forth. Speech rate is **4.8 words/s while speaking** (median; range 2.8–5.7, measured as words ÷ summed line spans, which runs slightly high on rapid back-and-forth; one clock check gave 4.8 words/s over a 10 s argument). Speech covers about **42 %** of runtime (range 23–60 %).
- **Montages are wordless** (8–16 s gaps in dialogue), carried by music.
- **A music bed runs the full length.** No silence was found in any reel (silencedetect −35 dB / 0.4 s). The mix sits at a constant level (about −14 LUFS momentary under dialogue, measured on DeukYhBBTKE) and **lifts 3–4 dB for the real-life tag**, where the energy drops in. Low booms hit time jumps.
- **SFX** punctuate the beats: phone dings for each order, camera shutter and flash, whooshes on whips, engine and exhaust pops.
- The specific music tracks were not identified, because this analysis can't listen. Treat the music notes above as measured shape, not genre.

---

## 10. Captions

Every reel burns in **one word at a time**, centred at about 45–60 % of frame height: bold condensed caps with a black outline, in white or yellow italic. There is a small hook title in the first second ("MOM SAID I'D FAIL 💀"). **Do not copy their caption text or exact look**; brands set their own caption style in the brand kit. The lesson is only that the hook title plus word captions make the reel work on mute.

---

## 11. Story templates (use one per video)

**A. "They said I'd fail"** (8 of 12 reels, including the 16.4M top reel)
Doubter (mom, dad, stepmom) confronts the hero over money (0–5 s) → stakes and deadline ("one week", "every dollar") → wordless grind montage → night low point → first sale ding → scale-up montage (the doubter joins in) → shared win ("We did it." / "No. We did.") → comic button (a closet full of new stock, the doubter's scream ECU) → real tag.

**B. "She chose money"** (3 reels: 8.2M, 6.2M, 4M)
Public rejection at a big romantic set piece (altar, Eiffel Tower, graduation) → rival flaunts wealth → hero alone (tear ECU, slow push) → grind montage → white flash and "X YEARS LATER" card → mirrored meeting, the ex begs → hero's smug one-liner and exit → real tag.

**C. Status-gap underdog** (1 reel, 7.6M)
Rich people mock the hero's junk → dare ("Just watch.") → satisfying macro proof montage → paid and recommended → growth montage → time-jump card → returns in a supercar → quotable line → scream button → real tag.

For brands, put the brand's moment in the montage and the tag. fomo: the trading or app screens are the "first sale ding" and the scale-up, and the real fomo screens are the closing tag. Iron Paws: the real bag is the turning-point object and the tag.

---

## 12. Quick checklist for the Director

- [ ] First line spoken at 0 s; it is a conflict, with a number in the first 5 s
- [ ] A dare or promise by about 5 s
- [ ] A wordless montage, shots about 0.4 s, using one of the "same pose, bigger world" or before/after devices
- [ ] A cold-blue night low point with a slow push-in, then a phone-screen ding
- [ ] Time jump via white flash and a card on a hero object (if the story spans time)
- [ ] Payoff mirrors the opening place and people; the hero's line is under 8 words
- [ ] Comic button: whip into the doubter's scream ECU
- [ ] Ends on about 2 s of the real brand element
- [ ] About 1 cut per second overall; nothing over 3 s except a dialogue two-shot or a continuous reveal move
- [ ] Characters stay the same in every shot (sheet attached); one saturated hero object per scene
- [ ] Nothing copied: no captions, lines, characters, logos or real footage from the reference reels
