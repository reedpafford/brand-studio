import { Fragment, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { useHost, voiceByKey, voiceRef } from "../cast/Presenter";
import { sampleOf, useVoiceList, type Voice } from "../library/Voices";
import { useVideoSettings } from "../projects/VideoSettings";
import { useRunPresses } from "../videos/runActions";
import { PlayButton } from "./libraryParts";
import { Choice, Popover } from "./Popover";
import { useLock } from "./useLock";

type SettingIn = components["schemas"]["SettingIn"];

/** A voice by the name the video knows it by (the narration's own key, or the setting's "stock:<key>" / "voice:<id>"):
 *  its row in the brand's list when it has one, else the key itself. */
function known(list: Voice[], key: string) {
  const v = voiceByKey(list, key);
  return v ? { name: v.name, sample: sampleOf(v), ref: voiceRef(v) } : { name: key.replace(/^stock:/, ""), sample: null, ref: /^(stock|voice):/.test(key) ? key : `stock:${key}` };
}

/** The voice a narrated or presenter video is read in, and swapping it (Reed: "Let the director pick and we can swap if
 *  needed"). Null on a video with no narration (Movie, Dialogue, a song). A swap is two of the current site's own
 *  requests, each its own press: picking sets the video's voice (free; cast/Presenter.tsx's pick), and "Read it in …"
 *  is Carry on (videos/runActions.ts), which on a delivered video opens a start card with the price of reading the
 *  narration again. Nothing is read before that card's press, and Undo is offered only until that card is open (a card
 *  left open after an Undo would still show its price). One press sends each once, however fast it is pressed (./useLock). `set`: a voice that is set but not
 *  read yet. Undo puts the setting back, free. `card`: the open start card's id; one a press here opened is put on
 *  screen once it is drawn (a phone stacks the chat over the film then), clear of the message box pinned under it. */
export function useNarrationVoice(id: number, fsId: number | null | undefined, brandId: number, card: number | undefined) {
  const queryClient = useQueryClient();
  const host = useHost(id).data;
  const said = host?.voice ?? null;
  const settings = useVideoSettings(id, said != null);
  const setting = settings.data?.voice ?? null;
  const list = useVoiceList(said != null ? brandId : 0);
  const voices = list.data?.voices ?? [];
  const { carry } = useRunPresses(id, fsId);
  const [was, setWas] = useState<{ of: string; back: string | null } | null>(null); // the last pick's Undo
  const opening = useRef(false); // Carry on is sent from here: its card is on its way
  const press = useMutation({
    mutationFn: async ({ set, go }: { set?: SettingIn; go?: boolean }) => {
      if (set) {
        const out = (await must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: id } }, body: set }))).data!;
        queryClient.setQueryData(["video-settings", id], out.settings);
        setWas(set.undo || !set.voice ? null : { of: set.voice, back: (out.was as { voice?: string | null }).voice ?? null });
      }
      opening.current = !!go;
      if (go) await carry.mutateAsync();
    },
    onError: () => void (opening.current = false),
    // The page's reads of what a press changes, and the chat Carry on is already reading again: the press is done
    // once the page shows it all.
    onSettled: () => Promise.all([...["host", "video-settings", "asks", "director", "run-progress"].map((key) => queryClient.invalidateQueries({ queryKey: [key, id] })), queryClient.invalidateQueries({ queryKey: ["freestyle", fsId ?? 0] }, { cancelRefetch: false })]),
  });
  const lock = useLock(press.isPending);
  const settled = !press.isPending;
  useEffect(() => {
    if (!card || !settled || !opening.current) return;
    opening.current = false;
    const ask = [...document.querySelectorAll(".studio .thread .ask")].at(-1);
    if (!ask || typeof ResizeObserver === "undefined") return;
    // What is over it can still fold (the earlier delivery note, once the new run says its first words): for a moment
    // the card is kept where it was put.
    const follow = new ResizeObserver(() => ask.scrollIntoView({ block: "center", behavior: "smooth" })); // once now, then on each change
    follow.observe(ask.closest(".thread")!);
    const done = setTimeout(() => follow.disconnect(), 3000);
    return () => (follow.disconnect(), clearTimeout(done));
  }, [card, settled]);
  if (said == null || settings.isPending || list.isPending) return null; // no narration, or not read yet: no row
  const send = (what: { set?: SettingIn; go?: boolean }) => lock((done) => press.mutate(what, { onSettled: done }));
  const used = known(voices, said);
  const usable = voices.filter((v) => v.state === "ready" || v.state === "may_expire");
  return {
    used,
    set: host?.voice_pending && setting ? known(voices, setting) : null,
    list: [...usable.filter((v) => v.kind !== "stock"), ...usable.filter((v) => v.kind === "stock")], // the brand's own, then the app's
    busy: press.isPending,
    error: press.error?.message ?? null,
    pick: (v: Voice) => send({ set: { voice: voiceRef(v) } }), // free, and Undo is one press away; "Read it in …" brings the priced card
    read: () => send({ go: true }),
    // The voice before the last pick; after a reload, the one the video is read in.
    undo: () => send({ set: { voice: was && was.of === setting ? was.back : used.ref, undo: true } }),
  };
}

/** "Narration voice" in the Cast view: the voice's name and its sample to play. `change`: the video is delivered and
 *  nothing is going or waiting, so another can be picked from the brand's voices and the app's, each with its sample;
 *  the pick only sets it. A voice set but not read yet says so, with "Read it in …", which opens the start card with
 *  its price (`change` again: with a start card open, the card is the press), and Undo (`undo`: it isn't running or
 *  archived and no card is open). */
export function NarrationVoice({ voice: n, change, undo }: { voice: NonNullable<ReturnType<typeof useNarrationVoice>>; change: boolean; undo: boolean }) {
  const now = n.set ?? n.used;
  return (
    <section className="nvoice" aria-label="Narration voice">
      <h3>Narration voice</h3>
      <div>
        {now.sample && <PlayButton key={now.sample} src={now.sample} of={`${now.name}’s sample`} />}
        <p>
          <b>{now.name}</b>
          {n.set && <small>not read yet · the video still plays in {n.used.name}</small>}
        </p>
        {n.set
          ? (change || undo) && (
              <span>
                {change && (
                  <button type="button" className="btn soft" disabled={n.busy} onClick={n.read}>
                    Read it in {n.set.name}
                  </button>
                )}
                {undo && (
                  <button type="button" className="btn ghost" disabled={n.busy} onClick={n.undo}>
                    Undo
                  </button>
                )}
              </span>
            )
          : change &&
            n.list.length > 0 && (
              <Popover
                label="Narration voice"
                end
                button={(b) => (
                  <button type="button" className="btn soft" disabled={n.busy} {...b}>
                    Change the voice
                    <ChevronDown size={14} strokeWidth={1.75} aria-hidden />
                  </button>
                )}
              >
                {(close) => (
                  <>
                    <p className="pe">Picking one is free. You see the price before it is read.</p>
                    {n.list.map((v, i) => {
                      const sample = sampleOf(v);
                      return (
                        <Fragment key={voiceRef(v)}>
                          {i > 0 && v.kind === "stock" && n.list[i - 1].kind !== "stock" && <h6>The app’s voices</h6>}
                          <div className="vpick">
                            {sample ? <PlayButton src={sample} of={`${v.name}’s sample`} /> : <span aria-hidden />}
                            <Choice checked={voiceRef(v) === n.used.ref} note={v.description} onPick={() => (close(), voiceRef(v) !== n.used.ref && n.pick(v))}>
                              {v.name}
                            </Choice>
                          </div>
                        </Fragment>
                      );
                    })}
                  </>
                )}
              </Popover>
            )}
      </div>
      {n.error && <p role="alert">{n.error}</p>}
    </section>
  );
}
