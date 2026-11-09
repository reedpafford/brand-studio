"""The director's mechanical steps (Reed, 8 Nov: "remove every wasteful call and turn, without
lowering quality"): where the next step is the only sensible one and needs no judgment, the
server takes it itself, with no Claude call. Each is logged in the run like a turn and goes
through the very checks the director's own move does (`director._act`): its limits, budgets,
holds and refusals. The judgment stays the director's: the treatment, the voice, the looks,
redraws, redos, picks, edits, fixes and the delivery note; the cast and places OK too when
something in it changed since an OK or someone shown isn't cast. On a run with notes (a
revision) the same steps are the server's once every note has been answered (Reed, 9 Nov)."""

SAID = "server"  # in a turn's input: the server took this step itself (no Claude call)


def move(state: dict) -> dict | None:
    """The next step when it's mechanical, else None (the director's turn). `state` is what
    the turn would read: <video> with `chat` and `allowed`, `questions` (one is open, or was
    answered since the last turn), `tried` (a still or take of this run failed: going on
    without it, or trying again, is the director's call), `reviews` (this run's stills
    reviews), `fixed` (each fault this run's watch of the cut found has had a fix since) and
    `in_cut` (the takes the newest cut was made from)."""

    def go(tool: str, why: str) -> dict:
        return {"tool": tool, "why": why, "clip_id": None, "take_id": None, "note": ""}

    if (not state.get("started") or state["being_made"] or state["held_for_owner"]
            or state["failed_since_last_turn"] or state.get("questions")):  # fmt: skip
        return None  # a question, an answer or a failure is read by the director
    if any(not m.get("answered") for m in state.get("chat") or []):
        return None  # an open note: what it asks is the director's
    clips, watch, cast = state["clips"], state.get("watch") or {}, state.get("cast_ok") or {}
    if (state["cut"] == "made" and not (state.get("timeline") or {}).get("changes")
            and not state.get("cut_failed") and not watch.get("current")
            and state["allowed"].get("watches_left", 0) > 0):  # fmt: skip
        return go("watch_cut", "all: the cut is made, so it's watched as a viewer meets it.")
    if state.get("plan") == "ready":
        return go("plan", "all: the plan is written; approving it makes the shots.")
    if state["shots"] != "ready" or state.get("too_long") or state["missing_looks"]:
        return None
    if cast.get("state") in ("ready", "not_ready") and not cast.get("asked"):
        changed = any(i.get("approval") == "changed" for i in cast.get("items") or [])
        if cast["state"] == "ready" and not state.get("no_role") and not changed:
            return go("ask_cast_ok", "all: every look is drawn; the cast and places are the "
                      "person's OK.")  # fmt: skip
        return None  # a change since their OK, or someone not cast: the director says what
    stills = state["stills"]
    if not stills["frames"]:
        return go("storyboard", "all: the shots and the cast are set; the storyboard is next.")
    if stills["drawn"] + stills["waiting"] < stills["frames"] and not state.get("tried"):
        return go("stills", "all: every frame with no still yet is drawn.")
    if stills["waiting"]:
        return go("wait", "all: the other stills wait for the cast and places OK.") if cast.get(
            "asked") else None  # fmt: skip
    review = state.get("stills_review") or {}
    if review.get("state") == "none":
        return go("review_stills", "all: the stills are drawn; each is checked against the "
                  "treatment.")  # fmt: skip
    if any(c["takes"] for c in clips):
        return _first_cut(state, clips, go)
    used = state["allowed"].get("redraws_used") or {}
    if (review.get("state") == "done" and not review.get("current") and used
            and state.get("reviews") == 1):  # fmt: skip
        return go("review_stills", "all: the redraws are drawn; the stills are checked again, "
                  "once.")  # fmt: skip
    most = state["allowed"].get("redraws_per_still", 2)
    clean = review.get("current") and review.get("ready") and not review.get("findings")
    spent = review.get("current") and (state.get("reviews", 0) >= 2 or all(
        used.get(f.get("shot_id"), 0) >= most for f in review.get("findings") or []))  # fmt: skip
    if (clean or spent) and (not clips or any(c["stale"] for c in clips)):
        return go("clip_prompts", "all: the stills tell the treatment, or no redraw is left; "
                  "the clip prompts are next.")  # fmt: skip
    return _first_takes(state, clips, go)


def _first_takes(state: dict, clips: list[dict], go) -> dict | None:
    """Every clip's first take at once, once each has its prompt (none waiting for the OK)."""
    bare = [c for c in clips if not c["takes"] and not c.get("talker")
            and not c.get("waits_for_cast")]  # fmt: skip
    if (not bare or state.get("tried") or any(c["stale"] for c in clips)
            or any(c["picked_take_id"] or c.get("against_notes") for c in bare)):  # fmt: skip
        return None
    return go("make_take", "all: every clip has its prompt; their first takes are made at once.")


def _clean(c: dict) -> bool:
    """The clip's newest take is picked and clean, with nothing else to judge in it (no word
    heard wrong or unscripted, no brand screen, no doubt)."""
    last = c["takes"][-1] if c["takes"] else None
    return not (last is None or last["verdict"] != "clean" or c["picked_take_id"] != last["id"]
                or last.get("unscripted") or last.get("set_aside") or c["stale"]
                or any(c.get(k) for k in ("old_take", "against_notes", "can_splice",
                                          "no_copy")))  # fmt: skip


def _first_cut(state: dict, clips: list[dict], go) -> dict | None:
    """The first cut once every take is in, picked and clean. The cut again once what changed
    since the last one is in (a trim, a mute, a remade take its watch kept) and each fault
    this run's watch found has had its fix. Else the remaining first takes (after the cast
    and places OK)."""
    if move := _first_takes(state, clips, go):
        return move
    if any(c.get("waits_for_cast") for c in clips):
        return None
    host = state.get("host")
    if host and host.get("state") != "ready":
        return None
    made = [c for c in clips if c["takes"] or not c.get("talker")]  # a talker's: at the cut
    timeline = state.get("timeline") or {}
    if state["cut"] == "out of date" or state["cut"] == "made" and timeline.get("changes"):
        if state.get("fixed") and all(
            c["picked_take_id"] and not c["stale"]
            and not any(c.get(k) for k in ("old_take", "against_notes"))
            and (c["picked_take_id"] in state.get("in_cut", ()) or _clean(c))
            for c in made
        ):  # fmt: skip
            return go("final_cut", "all: the fixes are in; the cut is made again.")
        return None
    if state["cut"] != "none" or not all(_clean(c) for c in made):
        return None
    return go("final_cut", "all: every clip has a clean take; the cut is made.")
