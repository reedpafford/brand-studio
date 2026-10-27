# Step: Look fit (a check on a made character sheet)
<!-- Inputs: the sheet image, then <character> (the look's description: age range, gender, role or job, then the look) and optional <role> (their part in the story). Output: LookFit. The server redoes a sheet that doesn't fit once, with look_fit_redo(...) as the change note, then shows advice if it still doesn't. -->

The image is a character turnaround sheet for an animated brand video: one character drawn three times (front, side, back) in a stylised 3D cartoon look with expressive eyes. The style never makes an adult look like a child: an adult still has an adult's height, build and face. Check that it shows the character in <character>, so a viewer reads the right person at a glance.

Judge only four things, as a viewer would:
- **Age range:** from body proportions, face, height and posture, allowing for the cartoon style. A child or teen drawn for an adult, an adult for a child, or someone elderly for a young role does not fit. A 30s character who looks 25 or 40 fits.
- **Gender:** as described.
- **Role or job:** only where the outfit plainly contradicts it (a school uniform on a teacher, a business suit on a toddler). A plain outfit that doesn't show the job fits.
- **Three views:** a front, a side and a back view of the same character. A sheet missing one of them does not fit ("draw all three views: front, side in profile, and back").

Everything else fits: the style, colours, hair, small outfit differences, the pose. An adult drawn with a child's proportions (a big head on a small body, a round baby face) does not fit, even in the cartoon style. When in doubt, it fits; only a clear mismatch is worth a redraw.

`seen` says who the sheet shows in a few words ("woman in her 40s"). When it doesn't fit, `problem` is one plain instruction for the redraw ("draw an adult woman in her 40s, not a girl").
