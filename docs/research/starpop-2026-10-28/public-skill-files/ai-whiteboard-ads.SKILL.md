---
name: whiteboard-explainer
description: "Activate when the user wants a presenter-led physical-whiteboard explainer where the board develops with the spoken argument. Not for narrator-led whiteboard animation, digital boards, or slides."
---

# How to make whiteboard explainers

Create a vertical, lip-synced presenter explainer in which the spoken argument and the physical whiteboard develop together.

The board is not background decoration: it is a planned sequence of readable states, and the presenter visibly traces each AI-generated addition as it appears.

This is a format workflow.

Follow the shared media, image, video, and speech foundations.

When the user wants to stay close to a specific analyzed reference, replicate-video owns the source keep/replace specification and script-adaptation gate; apply this skill's board planning and execution rules once the whiteboard format is confirmed.

## Hard invariants

1. Default to one vertical 9:16 social video. Let the copy and selected speech take determine the runtime; do not propose or target a duration, and do not ask the user to choose runtime, aspect ratio, destination, or count unless they explicitly request another deliverable.

2. This is an on-camera lip-sync workflow. The presenter delivers every spoken shot; do not offer narrator voiceover as an alternative. Talking-only shots and intentional pauses for drawing are allowed within this workflow; speech does not require continuous drawing.

3. The presenter must physically trace AI-generated handwriting and drawings as they appear. Do not offer editor-added text, overlays, or composited board writing as alternatives.

4. Obtain approval of the exact script before generating speech or visuals.

5. Generate one continuous speech take, analyze its real timing, and slice it only after the final take is selected.

6. Plan every board chapter from its fullest terminal state before generating any state image.

7. Generate and approve every required board-state image before generating any video that consumes those images.

8. Reattach canonical actor, room/board, wardrobe, and product canonical references whenever they appear. A prior generated state may guide board layout, but it never replaces a canonical reference.

9. Give each clip one physically performable main action: write or draw, point, or explain. Talking-only shots keep the board unchanged. A reset is a cut or its own wiping action, never an unexplained morph hidden inside a writing shot.

10. Board writing is intentional scene content, not a caption exception. Keep captions, subtitles, watermarks, and unrelated generated text out.

11. During every writing or drawing action, the presenter must look at the whiteboard and follow the marker tip with their eyes. They may address the camera before or after writing, but never while the marker is moving on the board.

12. Keep all physical movement at natural real-time human speed. Never accelerate hands or arms, use timelapse or speed ramps, or compress drawing to reach a target board state within a speech slice. Fit the board change to the available action time, not the other way around.

## Pipeline

### 1. Settle the format

State these workflow defaults as settled rather than asking about them:

- One vertical 9:16 social video

- No target duration; the approved copy and final speech take determine the runtime

- On-camera presenter lip-sync for every spoken shot

- AI-generated handwriting and drawings that the presenter visibly traces onto the physical board

Ask only for unresolved creative inputs that materially change the concept:

- Presenter identity, wardrobe, room, and physical whiteboard

- Core angle, argument, or script direction

- Product, topic, or audience only when current context does not already establish them

- Whether to closely adapt a supplied reference or create an original whiteboard concept, only when a reference is present

Batch the presenter and angle questions into one short reply.

Do not present the fixed workflow defaults as choices.

For a workspace product, establish its exact identity, detailed facts, and accurate visual references.

### 2. Lock script and speech

When a script must be written, adapted, or materially revised, apply the advertising foundations before presenting copy.

Write or adapt the script into short spoken shots.

Present every changed line and wait for approval.

Give each shot a purposeful visual action: add a necessary mark, point at existing content, or explain with the marker held away from the board.

Do not invent drawing or pad the spoken copy to occupy every shot.

The approved copy and final speech timing set the runtime; plan any intentional pauses needed for physical actions before generating speech.

For separately generated speech:

1. Confirm the voice.

2. Prepare one continuous voiceover take for the whole script.

3. Preserve intentional pauses needed for turning, reaching, drawing, and settling; never shorten the take to make the ad faster. Recheck the action budget after any audio edit.

4. Measure the actual final take and its word timings.

5. Map lines to exact word timings and divide the audio at natural phrase boundaries so every spoken video shot receives its matching lip-sync audio slice.

The selected take is the pacing source of truth.

Do not keep the reference video's old durations after the new speech exists.

### 3. Build the shot and board-state ledger

Before generating images, present one approved ledger with these columns:

| Shot | Spoken line | Duration | Action and motion budget | Board chapter | Start state | New marks or none | End state | Reserved future space | Seam |
| ---- | ----------- | -------- | ------------------------ | ------------- | ----------- | ----------------- | --------- | --------------------- | ---- |

For every shot, check:

- After allowing time to turn, reach the board, and settle or look back, can a real presenter complete the planned mark legibly at normal speed in the remaining writing window?

- Does the motion budget separately account for setup, drawing, and settling, with only physically plausible overlap with speech? Estimate conservatively from the actual strokes and reach; do not use a universal characters-per-second quota or claim an estimate was measured.

- Is there one main physical action rather than a chain of unrelated actions?

- Would talking, pointing, or holding the marker communicate this shot without any new marks? If so, use the same start and end board state.

- Does the presenter have a stable lane that does not cover current or future writing?

- Is the end state readable on a phone in under a second?

- Does the next shot continue this board, cut to a reset, or show a dedicated wipe?

Use short labels, large lettering, and simple marks.

Prefer one short label, number, arrow, circle, or simple shape per drawing action.

If it does not fit at natural speed, simplify the board copy or split the change across smaller intermediate states and available speech shots.

If more performance time is still necessary, propose an intentional pause or a revised shot grouping for approval and update the final audio and slices before generating video.

Do not invent extra dialogue, silently retime approved speech, or add unexplained extra spoken shots.

Keep each spoken line's meaning aligned with the board: do not have the presenter explain a completed multi-step diagram while only its first box exists.

Revise and approve the start/end state images when the planned change shrinks.

A prompt asking for one small mark must not still target an image containing the entire unfinished diagram.

## Terminal-state-first board planning

A board chapter is one uninterrupted accumulation of writing.

A reset starts a new chapter.

Plan each chapter backward:

1. Inventory every phrase, number, arrow, checkmark, and drawing that must exist by the chapter's end.

2. Reserve a presenter lane and the arm path needed to reach every writing zone.

3. Design the fullest terminal layout first. Assign every addition a fixed zone, alignment, text scale, and writing order.

4. Test that terminal state at the delivery size. If it is crowded, split the chapter and schedule a reset before generating anything.

5. Define earlier states by subtracting later additions from the terminal layout. Keep their future zones blank; never recenter partial content into those reserved areas.

6. Give every reset a separate clean-board start state. The number of state images follows the state graph, not a shots-plus-one formula.

Example chapter plan:

    +------------------------------------------------+
    |             EATING HEALTHY?                    |  top zone: shot 1
    |                    down arrow                  |
    |                                                |
    |             NUTRIENT GAPS                      |  middle zone: shot 2
    |             crossed-out plate                  |
    |                                                |
    |       LOW ENERGY / BRAIN FOG / GUT ISSUES      |  lower zone: shot 3
    +--------------------------------+---------------+
                                     | presenter lane|

The terminal state fills all three zones.

The shot 1 state keeps its line in the top zone while the middle and lower zones remain empty; it must not center the line vertically, because that would consume space already assigned to later shots.

When the user changes one state, recompute the rest of that chapter before generating downstream assets.

A local layout change is not approved until every later addition still fits.

## Generate the state images

Establish canonical references before the state sequence:

- Actor identity and wardrobe

- Canonical reference image of the room and blank board

- Canonical product reference when it appears

- Any distinctive marker color or handwriting treatment that must recur

Under Auto: GPT Image 2 (`gpt-image-2`; recommendation `image.whiteboard`). Tested default for board states needing text rendering, edit adherence, and consistent composition. Honor a capable pinned model or an explicit user choice.

Generate one chapter at a time:

1. Generate the chapter's terminal full-board state first and get approval.

2. Generate preceding partial and blank states backward from that layout.

3. Reattach the canonical actor and master room/board references to every state. Attach the approved terminal state only as the chapter layout reference.

4. Tell the image model exactly which existing marks remain, which later zones stay empty, and where the actor stands.

5. Generate only the next image whose dependencies exist. Do not generate the chapter's dependent images all at once.

Use this prompt structure:

    Physical whiteboard explainer still.
    reference image 1 = canonical presenter; preserve identity and wardrobe.
    reference image 2 = master room and blank whiteboard; preserve camera, board boundaries, lighting, and presenter lane.
    reference image 3 = approved terminal state for this board chapter; preserve its zone geometry, alignment, text scale, and handwriting treatment only.

    Create chapter [N], state [S].

    Keep [existing marks] exactly in their assigned zones.

    Leave [future zones] completely blank for later additions.

    The presenter stands in [lane and pose] without covering any current or reserved zone.

    The only intentional text is the listed whiteboard writing.

    No captions, subtitles, watermarks, or unrelated text.

For a terminal state, list every exact phrase and drawing.

For a reset state, use the master blank board and keep the board clean.

When a product appears, attach its canonical reference and preserve its packaging accurately.

Do not generate video until all state images and required audio slices exist and the user has approved the complete state sequence.

## Execute each video shot

| Need                                                    | Mode                                                                                                                     |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Spoken shot with a designed board progression           | Seedance 2 Fast references: start-state image, end-state target, canonical actor reference, canonical product reference when needed, and the shot audio slice |
| Spoken talking, pointing, or holding shot with no new marks | One unchanged board-state image plus the matching audio slice and canonical references in references on a capable lip-sync model |
| Clean-board reset                                       | Hard cut to a separately generated blank state, or a dedicated non-spoken clip whose only action is wiping the board     |
| Writing is too dense or repeatedly fails                | Shorten the board copy or split it across more traceable writing shots, then regenerate from the approved state images   |

Under Auto: Seedance 2 Fast (`seedance-2-fast`; recommendation `video.whiteboard`). Tested default for lip-synced board progression using state images and the matching shot audio slice as references. Use one shot per generation by default.

Multiple reference images plus audio are guidance, not exact frame anchors: describe the start and target roles clearly, but never promise pixel-exact endpoints.

Every spoken shot must attach its matching audio slice and direct the presenter to lip-sync it.

Only drawing shots trace a planned addition; talking-only shots explicitly preserve all marks and keep the marker away from the board.

Do not replace a spoken shot with an exact-frames narration workflow.

Write each video prompt in this order:

1. Physical whiteboard-explainer format and locked camera

2. Role-labelled references

3. Existing board marks that must remain unchanged

4. The one new phrase or drawing and its fixed zone, or explicitly no new marks for a talking-only shot

5. Presenter's budgeted chronological action and eye line: for drawing, turn head and eyes to the board before the marker touches it, keep looking at the board throughout the mark, then settle; for talking-only shots, explain or point without writing. Include camera-facing turns only when the action budget allows them.

6. Lip-sync direction tied to the attached shot audio

7. Preservation constraints, No captions., and No background music.

Every video prompt must include: "All movement happens at natural, real-time human speed.

No timelapse, fast-forward, speed ramps, or accelerated hand or arm movement.

Preserve the attached speech timing and lip-sync." Do not rely on a generic request for natural acting; explicitly direct the speed of the physical motion.

For drawing shots, explicitly emphasize the single writing action and include: "While writing or drawing, the presenter looks at the whiteboard and follows the marker tip with their eyes.

They do not look at the camera until the mark is complete." Preserve existing writing exactly and add only the planned new content in the reserved zone.

For talking-only shots, explicitly say the board remains unchanged and the marker never touches it; do not add a writing action just because this is a whiteboard video.

Example drawing direction after the timing check:

    She looks at the board and draws only the short connecting arrow, using deliberate continuous strokes at a comfortable writing pace while speaking.

    Once the arrow is complete, she lowers the marker and continues explaining.

    All other marks remain unchanged.

The motion-speed instruction is not a substitute for a feasible action budget.

If the target cannot be reached at real-time speed, revise the plan and target state before generating.

The recommended board-progression model accepts 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 second generations; check the selected model's capabilities when another model is chosen.

When a speech slice is shorter than the model minimum, merge it with an adjacent natural thought, add a planned pause or gesture and trim the tail in the editor, or use a capable shorter-duration model that accepts the state image and audio slice for lip-sync.

## Review and failure handling

Review every still for:

- Correct spelling and only the intended board text

- Stable actor, wardrobe, room, camera, and board boundaries

- Fixed zone placement across the chapter

- Reserved future zones still empty

- Presenter and arm path clear of current and future writing

- Terminal state readable at phone size

Review every clip for:

- Lip-sync and natural face visibility in every spoken clip

- Eye line stays on the whiteboard and follows the marker throughout every writing or drawing action; direct-to-camera gaze happens only before or after the mark

- Natural real-time arm and hand motion, with no acceleration during normal-speed dialogue

- One plausible main action within the available time; no new marks in talking-only shots

- Existing marks preserved and only the planned addition created

- Static or intentionally simple camera behavior

- No unexplained erasure, extra writing, captions, or music

- A usable seam into the next state

For sped-up drawing, recheck the physical-action budget and simplify or split the board change before retrying.

Revise any affected state images and get approval so the prompt and target image agree.

Test the corrected shot before regenerating the rest of the sequence.

Do not slow down or speed up a lip-synced clip in post to repair arm motion; that would also alter the face timing.

Regenerate a failed shot from the locked canonical references and approved state images, never from a captured frame of the failed video.

After two attempts fail for the same handwriting or text reason, stop spending generations and revise the board plan: shorten or rephrase the writing, simplify the marks, or split the action across more shots.

Keep the writing AI-generated and visibly traced.

Prompt checks cannot establish whether motion looks natural: inspect the rendered clip before accepting it.

After picture lock, assemble against the full speech take, trim handles, add cuts at planned resets, and add background music slightly longer than the finished edit at a low level beneath speech.

## Final self-check

- Is every changed script line approved?

- Did the kickoff default to vertical 9:16, copy-driven runtime, on-camera lip-sync, and AI-generated handwriting without asking the user to choose among alternatives or imposing a duration target?

- Does any written, adapted, or materially revised script satisfy the advertising foundations?

- Was the final speech take analyzed before shot durations were locked?

- Does every board chapter have an approved terminal layout and reserved future zones?

- Does every reset have a real cut, blank state, or dedicated wipe action?

- Were canonical references reattached to every dependent state?

- Do all required state images and audio slices exist before video generation?

- Does every spoken clip lip-sync its attached audio slice while performing one human-plausible action, with talking-only shots allowed to leave the board unchanged?

- Does every drawing shot have a feasible setup/drawing/settling budget and a target image containing only that feasible change?

- Does every video prompt require natural real-time motion and explicitly prohibit accelerated arms, timelapse, fast-forward, and speed ramps?

- Does every drawing prompt explicitly direct the presenter to look at the whiteboard throughout the mark and return their gaze to camera only afterward?

- Is every board addition AI-generated and visibly traced rather than added as editor text or an overlay?

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
