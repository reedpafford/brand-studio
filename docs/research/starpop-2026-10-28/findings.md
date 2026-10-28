# Starpop vs Brand Studio: one-page summary for Reed

Sources (read these for detail):
- [README.md](README.md): Starpop, from the session on your Mac. It has the feature map, all 13 skills tested, the test log (20.24 credits) and 45 screenshots.
- [ours.md](ours.md): Brand Studio today, from the repo and QA-Live's live runs.
- [public-skill-files/](public-skill-files/): the style guides Starpop publishes free on its site.

**Your verdict stands:** our flow and our outputs are better for script-led ads. Borrow ideas, don't rebuild. Everything below would come after the stabilization pass (rule 25).

## Who does what better (script-led Pixar UGC ads)

| Starpop does better | We do better |
|---|---|
| **Checks its own output.** It watches each clip, reads the transcript and flags problems such as a stray "hmm" or a wrong colour, then rerolls. | **The script is locked.** Dialogue stays word for word through every step (rule 19). Starpop rewrote your finished lyrics until you corrected it. |
| **Cheap fixes.** A bad voice line was re-voiced and re-edited for 0.5 credits, with no 8-credit video re-render. | **A real scene-by-scene board.** Breakdown → Storyboard → Clips, each shot approved before money is spent. Theirs is chat text. |
| **Hands off to editing software.** Premiere and DaVinci timelines with voice and music in sync, plus media files for CapCut. | **Reliability and refunds.** "Failed · credits returned". On Starpop, stuck jobs were charged and never delivered, with no retry and a Cancel that didn't work. |
| **Voice, music and captions in one place.** ElevenLabs and Fish Audio voices, Suno songs, captions added in their edit step. | **Cost control.** Per-video budget, the $75 cap, weekly allowances and an owner approvals queue. Editors never see dollars. |
| **Song ads**, timed to the real song (see below). | **Brand exactness rules.** The real bag and the fomo logo on screens, and the hero in every montage shot. Starpop invents packaging unless you upload a photo. |
| **Brand from a website.** Logo, colours, description and products are pulled from a URL. | **Undo everywhere**, step locks that say why in plain words, and "Out of date" marks after an upstream change. |
| **Many models**, cheap ones included (P-Image 0.25 credit per image). Model and cost are shown on every draft. | **Reel import keeps the reference's dialogue**, with a cast read and automatic looks for every role. |
| **Ad library.** 137k ranked Meta ads with one-click "Replicate". | **Owner/editor roles.** You publish scripts and editors make them. Starpop Solo has 1 seat and no approvals. |

Both have character sheets first and a priced approval before generating. Both lack comments on assets.

## The song-ads skill file vs what it actually did

| The public file ([song-ads.SKILL.md](public-skill-files/song-ads.SKILL.md)) says | What the Mac session saw |
|---|---|
| "When the user supplies lyrics, those are the song … preserve every word." | **Broken in practice.** When given a screenplay, it rewrote your finished lyrics; your own chat had to say "Those were finished lyrics". The keep-the-words rule only applies if it decides your input *is* lyrics. A pasted script doesn't count. |
| Write 2–3 song options (concept, lyrics, style, visual concept), recommend one, wait for a pick. | Matches, with 2 directions and one recommended. Claims were labelled "unverified". |
| Style line under 25 words, plus fixed text: "vocals start immediately, no instrumental intro … tight ending". Lyrics wrapped in `[Intro: vocals start immediately]` … `[End]`. | Couldn't check: the music step failed ("Couldn't complete this step.", no reason, no retry), and the manual Suno test was still spinning at 5m38s. |
| Song generated once, whole. Storyboard only after it exists, timed to its real word timestamps. Lip-sync only on shots marked SUNG (usually the hook and the last chorus); the rest is silent B-roll. | The plan in your own chat followed this (2 Suno takes, one marked preferred, storyboard to the real timing), but no finished song video was produced while we watched. |
| Captions are a separate layer, never in the picture. | Matches the Pixar test: captions were added in the edit step, not in the generated footage. |

**For us:** the file's method is sound. Its failure is exactly our rule 19. If we build song ads, finished lyrics are locked by default, and only "Write lyrics for me" lets the AI write them.

## Five ideas worth borrowing, ranked by value for script-led Pixar UGC ads

| # | Idea | Why it's worth it | Size |
|---|---|---|---|
| 1 | **Song ads with locked lyrics.** Paste lyrics (or get 2 directions), make 2 Suno takes and pick one, then storyboard to the song's real timing. The hero lip-syncs the hook and chorus; the rest is B-roll. | Your #1 pick, and a new format our script-first flow suits better than theirs. Needs a music model via Replicate and lip-sync clips from a song slice. | L |
| 2 | **Dialogue check on each take.** Transcribe the take, compare it with the script, and flag wrong words, another language, or stray sounds as Advice, with "Make another take". | Catches what QA-Live hit, like the take that switched to Mandarin, without anyone watching every clip. It checks words, not faces, so it fits rule 11. About 1 credit per take; needs your OK. | M |
| 3 | **Starpop's Pixar prompt blocks.** A fixed style paragraph, character paragraph and camera paragraph in every still, one motion line opening every clip, plus their failure/fix table ("reroll the same prompt before rewriting it"). | Cheap and likely lifts the look right away. **Needs your OK first:** rule 20 says prompting follows only the official Seedance and Nano Banana docs. | S |
| 4 | **Export to an editor.** A Premiere/DaVinci timeline (or a CapCut-ready folder) next to "Download all clips". | Editors who finish in their own tools get the cut in order, ready to trim. No AI and no cost. | M |
| 5 | **Brand from a website URL.** Pre-fill logo, colours, description and products for a new brand, with a review screen before saving. | Faster setup for each new client brand. Products still need real bag photos for exactness (rule 16). | M |

Considered and left out for now: model choice per project (videos stay 480p Seedance, rule 2), Branch/Revert (Undo and earlier takes already cover it), the ad library (big to build, and reel import already covers adapting a winner).
