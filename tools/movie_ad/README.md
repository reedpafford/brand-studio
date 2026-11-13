# Movie Ad 1 (RP5): the worked example

The files that made Movie Ad 1 for Palace Guard on 12 to 13 Nov 2026, kept as the worked example for `docs/next/working-a-video.md`. They are a record, not a product: they were run from the skopje workspace and reach the live site through Reed's upload tools (`bsapi`), so paths inside them point there.

- `plan.py`: the director's breakdown. The cast (the words each person's sheet was drawn from), the place pictures, each voice in a few words, what every picture is for, and all 25 clips exactly as they were sent: scene context, timed shots, one look line, one sound line. The three rounds of Reed's notes are the last blocks, each replacing the clips it corrects. `python3 plan.py` lists the clips and the price from their seconds.
- `film.py`: makes the cast, the sheets and the clips through the site; resumable, so nothing is asked for or paid for twice; stops at a figure (`CAP`).
- `review.py`: every clip looked at (a frame a second) and listened to (words heard against words planned) before Reed sees it.
- `cut.py`: the finish: the alarm's sound following its light, the time cards, the captions with the spoken word in yellow, the three hook versions.

Cost: $101.46 for three versions of about 6:38 each. Every paid step is in `ops/SPEND.md`.
