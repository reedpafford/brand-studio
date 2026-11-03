# Example ads: how to add one, and what a study holds

An example is a real ad that worked. We study it until we know how it was made and why it
works, so the director can make that kind of ad again from a new script, for any brand.

**A study is guidance.** Once it's merged, the writing steps read it for every video in its format or style, so a study goes in its own PR and only Reed's approval merges it (the guides-guard check).

## Where examples go

Every example belongs to one format or one style:

- **Format** = how the script reads: its structure, pacing and sound (for example `dialogue`,
  `song`, `narrated`, `zack-d`).
- **Style** = how it looks: the picture, light, colour and how the camera moves (for example
  `house`, `skeleton`, `claymation`).

Pick the one the example teaches best. If it teaches both, study it once under the format and
say in the style section which style it shows.

```
server/app/guides/formats/<format>/examples/<name>/study.md
server/app/guides/styles/<style>/examples/<name>/study.md
```

`<name>` is short, lower case, words joined by dashes, and says what the ad is
(`altar-rejection`, `kiss-cam`, `dads-way`). Only text goes in git: no videos, no frames. One
small contact sheet (under 150 KB) is allowed only if it truly helps; usually leave it out.

## How to drop an example in

1. Give us the link (Instagram, TikTok, YouTube) or the video file, and say which format or
   style it is an example of.
2. Someone runs the study kit on it. It is free and runs on the computer, no paid services:

   ```
   cd server
   uv run --group reel python -m scripts.study_example <link-or-file> formats/dialogue <name>
   ```

   It saves the video, the cuts, a frame from every shot, a contact sheet, the words with
   their times and the sound facts into `server/.study/<name>/` (kept out of git).
3. A model (in a working session, not a paid call from the app) looks at those frames and
   words and writes `study.md` using the outline below.
4. You read it. If something is wrong, edit it: the study is guidance, and only you change it.

Instagram often refuses downloads without a login. If the link fails, save the video yourself
and give the kit the file instead.

## What a study contains

Mark anything worked out rather than seen or heard with *(inferred)*.

1. **Source**: the link or file, who made it, when it was studied, how it was read.
2. **Length**: seconds, shot count, words spoken.
3. **The hook**: exactly what is seen and heard in the first 2 seconds.
4. **The script as spoken**: every line with its time and who says it.
5. **Shot by shot**: a table of time, shot size, camera move, what happens, line, and how it
   cuts to the next shot.
6. **Pacing**: cuts per 10 seconds, the longest and shortest holds, where it speeds up and
   slows down.
7. **Sound**: music or not, sound effects, silences, how loud.
8. **On-screen text**: captions, cards, labels, and their look.
9. **The format pattern**: how the script reads and is built, beat by beat.
10. **The style pattern**: the look, light, colour and how the camera behaves.
11. **Why it works**: for a viewer, second by second.
12. **How the director recreates this from a new script**: the recipe that carries over, line
    to beat to picture, and what **not** to copy (things that belong to that brand or only
    worked once).
