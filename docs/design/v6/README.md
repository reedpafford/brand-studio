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

### The frame and folder tree

| Board | State |
|---|---|
| [S0-01](boards/S0-01.jpg) | Tree states: none, nested, drag, rename, menu, delete + Undo, editor |

### Brand home: an open folder

| Board | State |
|---|---|
| [S1-01](boards/S1-01.jpg) | Loading |
| [S1-02](boards/S1-02.jpg) | Brand-new brand · set-up list |
| [S1-03](boards/S1-03.jpg) | Empty folder |
| [S1-04](boards/S1-04.jpg) | Normal folder · owner |
| [S1-05](boards/S1-05.jpg) | 124 ideas · list view, sort, filter, search |
| [S1-06](boards/S1-06.jpg) | Archived ideas |
| [S1-07](boards/S1-07.jpg) | Several selected · Move, Archive |
| [S1-08](boards/S1-08.jpg) | Normal folder · editor (credits) |

### New video

| Board | State |
|---|---|
| [S2-01](boards/S2-01.jpg) | Empty |
| [S2-02](boards/S2-02.jpg) | Filled in · a style sample playing · price shown (owner) |
| [S2-03](boards/S2-03.jpg) | A format and a style that are off |
| [S2-04](boards/S2-04.jpg) | Editor’s pasted script · held for the owner |
| [S2-05](boards/S2-05.jpg) | Editor · over the video’s budget · held |
| [S2-06](boards/S2-06.jpg) | From a saved script |
| [S2-07](boards/S2-07.jpg) | Use a reel |

### The video: chat + preview panel

| Board | State |
|---|---|
| [S3-01](boards/S3-01.jpg) | New idea, before the first move |
| [S3-02](boards/S3-02.jpg) | Treatment posted · start-of-run OK (owner) |
| [S3-03](boards/S3-03.jpg) | Working · progress card folded |
| [S3-04](boards/S3-04.jpg) | Working · progress card open |
| [S3-05](boards/S3-05.jpg) | Asking · one question, the rest carries on |
| [S3-06](boards/S3-06.jpg) | Waiting for the owner’s OK · owner |
| [S3-07](boards/S3-07.jpg) | Waiting for the owner’s OK · editor |
| [S3-08](boards/S3-08.jpg) | Stopped by a person |
| [S3-09](boards/S3-09.jpg) | Delivered · owner |
| [S3-10](boards/S3-10.jpg) | Delivered · editor |
| [S3-11](boards/S3-11.jpg) | A step failed · one-click fix |
| [S3-12](boards/S3-12.jpg) | Revising after a note |
| [S3-13](boards/S3-13.jpg) | Long Movie · 118 clips · when Movie is on |
| [S3-14](boards/S3-14.jpg) | Editor asks to change a locked line |
| [S3-15](boards/S3-15.jpg) | Loading |
| [S3-16](boards/S3-16.jpg) | Offline · the director keeps working |

### Ask cards

| Board | State |
|---|---|
| [S4-01](boards/S4-01.jpg) | Kinds 1 of 2: cast, presenter, voice, place, product, brand item |
| [S4-02](boards/S4-02.jpg) | Kinds 2 of 2: story choice, open question, start OK, budget |
| [S4-03](boards/S4-03.jpg) | States: uploading, generating, ready, answered, not needed, failed, held, several |
| [S4-04](boards/S4-04.jpg) | In context: generated options ready · when Movie is on |

### Cast and presenter

| Board | State |
|---|---|
| [S5-01](boards/S5-01.jpg) | Cast · owner · one role needs a look |
| [S5-02](boards/S5-02.jpg) | Presenter: avatar, voice, how it appears |
| [S5-03](boards/S5-03.jpg) | Role states sheet |
| [S5-04](boards/S5-04.jpg) | Cast · editor (credits) |

### Clips

| Board | State |
|---|---|
| [S6-01](boards/S6-01.jpg) | A short video · 6 clips |
| [S6-02](boards/S6-02.jpg) | One clip open · takes, prompt, model and why, actions |
| [S6-03](boards/S6-03.jpg) | Found by the director’s watch · what it found and redid |
| [S6-04](boards/S6-04.jpg) | A long video · 118 clips grouped by scene · when Movie is on |
| [S6-05](boards/S6-05.jpg) | Row states sheet: making, redone, flagged, failed, waiting, text found |
| [S6-06](boards/S6-06.jpg) | One clip open · editor (credits) |

### Cut editor

| Board | State |
|---|---|
| [S7-01](boards/S7-01.jpg) | Cut ready · a B-roll piece selected |
| [S7-02](boards/S7-02.jpg) | A person editing · unsaved changes · ducking the music |
| [S7-03](boards/S7-03.jpg) | The director editing · its edits marked, each with Undo |
| [S7-04](boards/S7-04.jpg) | Building the first cut |
| [S7-05](boards/S7-05.jpg) | Re-making the cut after changes |
| [S7-06](boards/S7-06.jpg) | Making the cut failed · one-click fix |
| [S7-07](boards/S7-07.jpg) | Editor’s view (credits) |

### Brand library

| Board | State |
|---|---|
| [S8-01](boards/S8-01.jpg) | Characters · owner |
| [S8-02](boards/S8-02.jpg) | An empty brand |
| [S8-03](boards/S8-03.jpg) | One item open · versions, where it’s used |
| [S8-04](boards/S8-04.jpg) | Presenters and voices |
| [S8-05](boards/S8-05.jpg) | Brand kit (fomo: real logo and screens) |
| [S8-06](boards/S8-06.jpg) | Products (Iron Paws: real bag) |
| [S8-07](boards/S8-07.jpg) | Generating a new character · importing from a website |
| [S8-08](boards/S8-08.jpg) | Editor’s view · archived shown |

### Needs you

| Board | State |
|---|---|
| [S9-01](boards/S9-01.jpg) | Owner’s inbox · questions, money, stuck |

### Phone (390)

| Board | State |
|---|---|
| [P-01](boards/P-01.jpg) | Brand and its folders |
| [P-02](boards/P-02.jpg) | An open folder |
| [P-03](boards/P-03.jpg) | Filled in · price shown |
| [P-04](boards/P-04.jpg) | Chat · working |
| [P-05](boards/P-05.jpg) | Preview · the delivered cut |
| [P-06](boards/P-06.jpg) | Asking · the card in the chat, pinned bar |
| [P-07](boards/P-07.jpg) | Waiting for the owner’s OK · editor |
| [P-08](boards/P-08.jpg) | Chat · delivered with the note |
| [P-09](boards/P-09.jpg) | Preview · Cast |
| [P-10](boards/P-10.jpg) | Preview · Clips, 118 grouped by scene |
| [P-11](boards/P-11.jpg) | One clip open |
| [P-12](boards/P-12.jpg) | The cut on a phone: play, edits, ask |
| [P-13](boards/P-13.jpg) | Characters |
| [P-14](boards/P-14.jpg) | Owner’s inbox |
| [P-15](boards/P-15.jpg) | Ask card · options ready |

77 boards in all: 62 desktop (1440) and sheets, 15 phone (390).
