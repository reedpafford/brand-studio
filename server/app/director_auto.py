"""The director's mechanical steps (Reed, 8 Nov: "remove every wasteful call and turn, without
lowering quality"): where the next step is the only sensible one and needs no judgment, the
server takes it itself, with no Claude call. Each is logged in the run like a turn and goes
through the very checks the director's own move does (`director._act`): its limits, budgets,
holds and refusals. The judgment stays the director's: the treatment, the voice, the looks
and the cast OK, redraws, redos, picks, edits, fixes and the delivery note."""

SAID = "server"  # in a turn's input: the server took this step itself (no Claude call)


def move(state: dict) -> dict | None:
    """The next step when it's mechanical, else None (the director's turn). `state` is what
    the turn would read: <video> with `chat` and `allowed`, `questions` (one is open, or was
    answered since the last turn) and `tried` (a still or take of this run failed: going on
    without it, or trying again, is the director's call)."""

    def go(tool: str, why: str) -> dict:
        return {"tool": tool, "why": why, "clip_id": None, "take_id": None, "note": ""}

    if (state["being_made"] or state["held_for_owner"]
            or state["failed_since_last_turn"] or state.get("questions")):  # fmt: skip
        return None  # a question, an answer or a failure is read by the director
    notes = state.get("chat") or []
    if any(not m.get("answered") for m in notes):
        return None
    clips, watch, cast = state["clips"], state.get("watch") or {}, state.get("cast_ok") or {}
    started = state.get("started")  # before Make it, only approving its written plan
    if (started and state["cut"] == "made" and not (state.get("timeline") or {}).get("changes")
            and not state.get("cut_failed") and not watch.get("current")
            and state["allowed"].get("watches_left", 0) > 0):  # fmt: skip
        return go("watch_cut", "all: the cut is made, so it's watched as a viewer meets it.")
    if notes:  # a run with notes: every other step is checked against them by the director
        return None
    if state.get("plan") == "ready":
        return go("plan", "all: the plan is written; approving it makes the shots.")
    if not started or state["shots"] != "ready" or state.get("too_long") or state["missing_looks"]:
        return None
    if cast.get("state") in ("ready", "not_ready") and not cast.get("asked"):
        return None  # the director assembles the cast and places and asks for the OK
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
    clean = review.get("current") and review.get("ready") and not review.get("findings")
    if clean and (not clips or any(c["stale"] for c in clips)):
        return go("clip_prompts", "all: the stills tell the treatment; the clip prompts are next.")
    return _first_takes(state, clips, go)


def _first_takes(state: dict, clips: list[dict], go) -> dict | None:
    """Every clip's first take at once, once each has its prompt (none waiting for the OK)."""
    bare = [c for c in clips if not c["takes"] and not c.get("talker")
            and not c.get("waits_for_cast")]  # fmt: skip
    if (not bare or state.get("tried") or any(c["stale"] for c in clips)
            or any(c["picked_take_id"] or c.get("against_notes") for c in bare)):  # fmt: skip
        return None
    return go("make_take", "all: every clip has its prompt; their first takes are made at once.")


def _first_cut(state: dict, clips: list[dict], go) -> dict | None:
    """The first cut once every take is in, picked and clean, with nothing else to judge in it
    (no word heard wrong or unscripted, no brand screen, no doubt); else the remaining first
    takes (after the cast and places OK)."""
    if move := _first_takes(state, clips, go):
        return move
    if state["cut"] != "none" or any(c.get("waits_for_cast") for c in clips):
        return None
    host = state.get("host")
    if host and host.get("state") != "ready":
        return None
    for c in clips:
        if c.get("talker") and not c["takes"]:
            continue  # cut from the talker's take at the cut
        last = c["takes"][-1] if c["takes"] else None
        if (last is None or last["verdict"] != "clean" or c["picked_take_id"] != last["id"]
                or last.get("unscripted") or last.get("set_aside") or c["stale"]
                or any(c.get(k) for k in ("old_take", "against_notes", "can_splice", "no_copy",
                                          "redo"))):  # fmt: skip
            return None
    return go("final_cut", "all: every clip has a clean take; the cut is made.")
