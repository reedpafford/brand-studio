import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Mic } from "lucide-react";
import { api, must } from "../api/client";
import { Badge, Button, Dialog, Menu, MenuItem } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import type { Script } from "./useScript";

const FORMAT: Record<string, string> = { story: "Dialogue", song: "Song", narrated: "Narrated" };
type Swap = "story" | "narrated";
const ASK: Record<Swap, { title: string; body: string }> = {
  narrated: { title: "Make this Narrated?", body: "One voice will read it; Cast keeps its roles but nobody speaks on camera." },
  story: { title: "Make this Dialogue?", body: "People speak their lines on camera. A narration already made is kept for when it comes back." },
};

/** Changing Dialogue ↔ Narrated with a confirm and Undo (flows ST0; Next-Server's PATCH /scripts/{id} {kind}, #907). */
function useSwap(s: Script) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const set = (kind: Swap) => must(api.PATCH("/scripts/{script_id}", { params: { path: { script_id: s.id } }, body: { kind } }));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
  const was = s.kind as Swap;
  return useMutation({
    mutationFn: set,
    onSuccess: async (_r, kind) => {
      await refresh();
      toast(`It's ${FORMAT[kind]} now.`, () => void set(was).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
    },
  });
}

/** The format in the script header (ST0): "Dialogue ▾" or "Narrated ▾" on a draft; a song, or anything published, is a plain chip. */
export function FormatSetting({ script: s }: { script: Script }) {
  const swap = useSwap(s);
  const [asking, setAsking] = useState<Swap | null>(null);
  const name = FORMAT[s.kind] ?? "Dialogue";
  if (s.published || (s.kind !== "story" && s.kind !== "narrated")) return <Badge>{name}</Badge>;
  return (
    <>
      <Menu title="Format" trigger={(t) => <Button variant="ghost" dense trailing={ChevronDown} busy={swap.isPending} aria-label={`Format: ${name}`} {...t}>{name}</Button>}>
        {(close) => (
          <>
            {(["story", "narrated"] as const).map((k) => (
              <MenuItem key={k} onClick={() => { close(); if (k !== s.kind) setAsking(k); }}>
                {FORMAT[k]}{k === s.kind ? " ✓" : ""}
              </MenuItem>
            ))}
          </>
        )}
      </Menu>
      {swap.isError && <p role="alert" className={errorClass}>{swap.error.message}</p>}
      {asking && (
        <Dialog title={ASK[asking].title} cancelLabel="Not yet" actionLabel="Change" busy={swap.isPending} onCancel={() => setAsking(null)} onConfirm={() => { swap.mutate(asking); setAsking(null); }}>
          {ASK[asking].body}
        </Dialog>
      )}
    </>
  );
}

/** The Director's narrator check on the Script step (ST0, N1): Advice only, never a block. */
export function FormatAdvice({ script: s }: { script: Script }) {
  const swap = useSwap(s);
  const [asking, setAsking] = useState(false);
  const v = s.versions.find((x) => x.slot === 0);
  if (!v || s.published) return null;
  if (s.kind === "story" && v.reads_narrated)
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm" role="status">
        <Mic size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
        <span className="min-w-0 flex-1">This reads as narrated. Make it Narrated?</span>
        <Button variant="secondary" dense busy={swap.isPending} onClick={() => setAsking(true)}>Make it Narrated</Button>
        {swap.isError && <p role="alert" className={`w-full ${errorClass}`}>{swap.error.message}</p>}
        {asking && (
          <Dialog title={ASK.narrated.title} cancelLabel="Not yet" actionLabel="Change" busy={swap.isPending} onCancel={() => setAsking(false)} onConfirm={() => { swap.mutate("narrated"); setAsking(false); }}>
            {ASK.narrated.body}
          </Dialog>
        )}
      </div>
    );
  if (s.kind === "narrated" && (v.dialogue_lines ?? []).length > 0)
    return (
      <ul className="space-y-1 text-sm text-warning" aria-label="Lines spoken on camera">
        {v.dialogue_lines.map((d) => (
          <li key={d.line}>
            Line {d.line}, "{d.text}": this line is spoken on camera, but a Narrated script has one voice. The narrator will read it.
          </li>
        ))}
      </ul>
    );
  return null;
}
