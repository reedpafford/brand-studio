# Brand Studio v6 wireframes: the director-first studio

For Reed. Design only: nothing here is built, and nothing here spent money. Approved by Reed on 3 Nov.

**What changes from v5.** Each video idea is one chat with the director, like working with the agent sessions. A preview panel beside the chat shows the work: the plan, the cast, the clips and the cut. The video is drawn everywhere as a strip of real frames, scene by scene. It fills in as clips are made, and clips the director changed stay outlined until you've watched them. Ideas live in free folders inside each brand. When the director can't decide something, it asks with a card: pick something saved, upload, reply, or generate options with the price first. It keeps working on everything else while it waits.

**Kept from v5 (rule 33).** The Linear-style light theme, Inter, one indigo button for each screen's main press, statuses as a dot plus words, the rail, and Needs you. Scripts, Media, Usage, Team and Settings stay as v5 draws them.

**Pictures.** Every picture is real:
- Frames marked "Test sample" come from the paid tests of 3 Nov (`kuala-lumpur/.context/tests`), not from the site.
- The fomo House frames (Marcus in the rain, the coins), the "Goth GF" sheet, fomo's logo and app screens, and the Iron Paws bag are site output or real brand files.

**Read with these.**
- [flow.md](flow.md): from an idea to the delivered cut, and what the owner and an editor each see.
- [coverage.md](coverage.md): every Current rule, every point of the director brief and every ledger decision, mapped to the board that handles it, or "not covered" with the reason.
- [review.md](review.md): the outside review, what was fixed, and Reed's answers.
- [build-plan.md](build-plan.md): the small PRs that build it, and who builds each.

**Re-render.** `cd src && python3 b_s3.py && python3 render.py S3`. Each `b_*.py` writes its boards' HTML; `render.py` turns them into JPGs with headless Chrome at 1x.

## Boards
