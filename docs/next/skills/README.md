# Reed's skill files (source material)

Reed's own skill files for our looks and ad formats, copied word for word.
They are the source the Director folds into the site's prompt files. The site reads the prompt files, not these.

| File | Kind | Folds into |
| --- | --- | --- |
| disney-pixar.md | Look | server/app/prompts/styles/disney-pixar.md |
| claymation.md | Look (4 sub-styles) | server/app/prompts/styles/claymation.md |
| paper.md | Look (5 sub-styles) | server/app/prompts/styles/paper.md |
| song-ad.md | Ad format | styles/song.md, song_directions.md, song_breakdown.md, song_clip_prompts.md |
| skeleton-ad.md | Ad format + look | styles/skeleton.md and the narrated steps |
| anime-comic.md | Look | server/app/prompts/styles/anime-comic.md |
| zack-d.md | Ad format (blue-world explainer) | styles/zack-d.md and the narrated steps |

Not usable as written in zack-d.md: the Starpop image ids, plate download links, Fish Audio voice ids and the named music track are Starpop's. The site does not fetch them; any plate, voice or music choice there goes to Reed first.

Site rules still win where they differ: story logic never becomes a rule, footage stays text-free, studio names only inside the Disney Pixar look, and the director thinks rather than follows bans.
