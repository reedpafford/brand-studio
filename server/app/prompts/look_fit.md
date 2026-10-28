# Step: Look fit (a check on a made character sheet)
<!-- Inputs: the sheet image, then <character> (the look's description: age range, gender, role or job, then the look) optional <role> (their part in the story) and optional <role_text> (the role's name and description as written, to be put right when the sheet contradicts them). Output: LookFit. The server redoes a sheet that doesn't fit once, with look_fit_redo(...) as the change note, then shows advice if it still doesn't. -->

The image is a character turnaround sheet for an animated brand video: one character drawn three times (front, side, back) in a stylised 3D cartoon look with expressive eyes. The style never makes an adult look like a child: an adult still has an adult's height, build and face. Check that it shows the character in <character>, so a viewer reads the right person at a glance.

Judge only four things, as a viewer would:
- **Age range:** from body proportions, face, height and posture, allowing for the cartoon style. A child or teen drawn for an adult, an adult for a child, or someone elderly for a young role does not fit. A 30s character who looks 25 or 40 fits.
- **Gender:** as described.
- **Role or job:** only where the outfit plainly contradicts it (a school uniform on a teacher, a business suit on a toddler). A plain outfit that doesn't show the job fits.
- **Three views:** a front, a side and a back view of the same character. A sheet missing one of them does not fit ("draw all three views: front, side in profile, and back").

Everything else fits: the style, colours, hair, small outfit differences, the pose. An adult drawn with a child's proportions (a big head on a small body, a round baby face) does not fit, even in the cartoon style. When in doubt, it fits; only a clear mismatch is worth a redraw.

`seen` says who the sheet shows in a few words ("woman in her 40s"). When it doesn't fit, `problem` is one plain instruction for the redraw ("draw an adult woman in her 40s, not a girl").

**The role's own words (<role_text>, when given):** its name and description were written before the look was made, and an editor may since have changed the look (a French bulldog drawn for "Biscuit, the golden dog… golden retriever, thick golden coat"). The sheet is now the truth. When the role's words plainly contradict what the sheet shows (species, breed, colouring, hair, age range, gender), rewrite them to match: `role_name` keeps the name word for word up to its first comma and changes only what follows, and `role_description` is the whole description with only the contradicting words changed, its personality, job and story kept, and no appearance the sheet doesn't plainly show added (no new colours or marks). Details the sheet doesn't show (a voice, a habit) never contradict it. Leave a field empty when its words already fit. This is independent of `fits`.
