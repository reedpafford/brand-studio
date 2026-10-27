# Merge roles, and "These may be the same person"

Reed, 2026-10-27 (DECISIONS, duplicate roles): one person must never become two roles, e.g. "Kimchi, Nate's rich friend" and "His friend with the supercar". The cast read already matches them on its own. This spec covers the two manual parts: **Merge into…** on a role, and the flag for likely duplicates. Nothing merges without a person confirming it, except the cast read's own matching.

It applies to a script's **Cast** step (`variations-characters-publish.md` §5) and a video's **Assets** roles (`video-flow.md` §2).

## 1. Merge into…
**Where:** in the role's `Ellipsis` menu, as **Merge into…** (`Merge` icon), above **Remove role**. On Assets it's in the card's `Ellipsis` menu.
- If there's no other role, it's disabled, with "There's no other role to merge into."
- **Who:** on Cast, the person who can edit the cast (Reed, or the editor whose script it is). On Assets, whoever is making the video.

**The dialog** (a sheet on phone), titled "Merge {role} into…", e.g. "Merge His friend with the supercar into…":
```
Who is this the same person as?
(•) Kimchi · Helper · Late 20s · man · Locked
( ) Nate · Main · Early 30s · man
( ) Mia · Main · Late 20s · woman

What moves to Kimchi (meta heading)
· 3 shots: 1.2, 2.1, 3.4
· 5 lines in the script: A lines 4 and 7, B lines 4, 6 and 9
  The words stay exactly as written; only who says them changes.
· Kimchi keeps Kimchi's look. The look made for His friend with the supercar isn't used any more, but it isn't deleted.

[Cancel]                                         [Merge · Free]
```
- **The list:** every other role, as a radio list (44px rows on phone). Each row shows the name, kind and facts line (`video-flow.md` §2), and the `Lock` "Locked" badge when the role is locked. Nothing is picked at first.
- **What moves** fills in once a role is picked. It's free to show, and it names exactly what changes:
  - **Shots:** the shots this role is in, by number. On Assets, they're this video's shots.
  - **Script lines:** the lines this role says or is named in, by version and line number. Dialogue never changes (README): the spoken words stay as written, and only the speaker's name in the line changes.
  - **The look,** in words, one of these:
    - The picked role is locked: "{Target} keeps {Target}'s look." It's never changed.
    - The merged role had a look (locked, or made for this script or video only): "The look made for {role} isn't used any more, but it isn't deleted." It stays in its owner's list (Cast & places, or the script's or video's own looks), so it can be picked again.
    - Neither has a look: nothing is said.
- **The button:** **Merge** (amber in the dialog), with "Free" in meta beside it. It's disabled with "Pick who this is the same person as" until a role is picked.
- **After:**
  - The merged role is gone from the list, and the picked role's "In" line and shot count grow.
  - Toast: "Merged into Kimchi. 3 shots and 5 lines moved." with **Undo** (8 s). Undo brings the role back with its shots, lines and look exactly as they were.
  - On a video, the stills and clips of the moved shots follow the cast-change rules: frames are rewritten, and stills are redrawn within the budget (`change-notes.md` §3).
- **Where it changes things:**
  - On Cast, it changes the script: every version and its cast.
  - On Assets, it changes this video only (its shots and its copy of the breakdown). The script's cast stays as it is, and the dialog says so in meta under the title: "This changes this video only."

## 2. "These may be the same person"
The server flags two roles that look like one person (similar descriptions, the same relation to someone, never in the same shot). Reed sees the flag, and so does an editor with the script, on Cast and on Assets.
- **Where:** a note at the top of the roles list (`warning-soft`, `Users` icon), one per pair:
  ```
  These may be the same person: Kimchi and His friend with the supercar.
  Both are described as Nate's friend, and they're never in the same shot. (meta, the server's reason)
  [Merge] (secondary dense)   [They're different] (ghost dense)
  ```
  - Each of the two rows also gets the badge "May be the same as {other}" (warning). Tapping it scrolls to the note and outlines it for 1.5 s.
- **Merge** opens the dialog from §1 for the less specific role, with the named one already picked (the server suggests which way: `into`). The person can still pick another role in the list.
- **They're different** dismisses the pair for good: the note and badges go, and the server never flags that pair again. Toast: "Kept as two roles." with **Undo** (8 s).
  - **On Assets** (Producer, 2026-10-27; follow-up to #590), **They're different** dismisses the pair for this video only: the note and badges go on this video, and the script's Cast still shows the pair. Same toast and Undo. Until its route lands, Assets shows the note with **Merge** only (as built in #590).
- **Several pairs:** one note per pair, at most three. More than three gather under "{n} more pairs may be the same person" (a disclosure, closed).
- **It never blocks** Next or anything else. It's advice, so it's neutral in wording, and it never names Reed.

## Data the screens need (server)
- **Merge (free):** `POST /scripts/{id}/cast/{slot_id}/merge {into_slot_id}`. On a video, the same route is under `/projects/{id}/assets/slots/{slot_id}/merge`, changing the video only.
  - It returns `{moved: {shots: [ids], lines: [{version, line}]}, look_unused: {name} | null}`.
  - `GET …/merge/preview?into=` returns the same, without changing anything, for the dialog.
  - `POST …/merge/undo {token}` puts everything back.
  - It refuses a role merged into itself, and roles from another script, in plain words.
- **Flags:** the cast and assets replies carry `maybe_same: [{a_slot_id, b_slot_id, into_slot_id, why}]`, where `why` is the plain reason and `into_slot_id` is the role to keep.
  - `POST …/cast/maybe-same/dismiss {a_slot_id, b_slot_id}` dismisses a pair for good.
  - `DELETE` on it is the Undo.
  - On a video: `POST /projects/{id}/assets/maybe-same/dismiss {a_slot_id, b_slot_id}` dismisses the pair for that video only, with `DELETE` as its Undo (Builder-Server-3).
- A merged slot keeps its look record unchanged (not deleted, not archived). It's only unlinked from the role.
