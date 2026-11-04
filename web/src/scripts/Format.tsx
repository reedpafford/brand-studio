import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Mic } from "lucide-react";
import { api, must } from "../api/client";
import { Badge, Button, Dialog, Menu, MenuItem } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useSearchParams } from "react-router-dom";
import { PickLabel, pickClass } from "./ScriptFrame";
import { stepsFor } from "./flow";
import { useFormats, type Format } from "./useFormats";
import type { Script } from "./useScript";

/** Another format's confirm: its blurb says what changes. Leaving Narrated keeps the narration already made. */
const ask = (f: Format, s: Script) => ({ title: `Make this ${f.name}?`, body: f.blurb + (f.engine === "story" && s.kind === "narrated" ? " A narration already made is kept for when it comes back." : "") });

/** Changing format (Dialogue ↔ Narrated and any other format of those engines) with a confirm and Undo (flows ST0; PATCH /scripts/{id} {format}). */
function useSwap(s: Script) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const set = (id: string) => must(api.PATCH("/scripts/{script_id}", { params: { path: { script_id: s.id } }, body: { format: id } }));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
  const was = s.format;
  const [params, setParams] = useSearchParams();
  return useMutation({
    mutationFn: (f: Format) => set(f.id),
    onSuccess: async (_r, f) => {
      await refresh();
      // A step the new format doesn't have (Narration, on a Dialogue script) gives way to Script (QA-2).
      const step = params.get("step");
      if (step && !stepsFor({ kind: f.engine }).some((x) => x.id === step)) setParams((p) => { p.set("step", "script"); return p; }, { replace: true });
      toast(`It's ${f.name} now.`, () => void set(was).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
    },
  });
}

/** The format in the script header (ST0): "Dialogue ▾" on a draft; a song, or anything published, is a plain chip. */
export function FormatSetting({ script: s }: { script: Script }) {
  const swap = useSwap(s);
  const formats = useFormats().data ?? [];
  const [asking, setAsking] = useState<Format | null>(null);
  const name = formats.find((f) => f.id === s.format)?.name ?? s.format;
  if (s.published || s.kind === "song") return <Badge>Type: {name}</Badge>;
  return (
    <>
      <Menu title="Type" trigger={(t) => <Button variant="ghost" dense trailing={ChevronDown} busy={swap.isPending} className={pickClass} aria-label={`Type: ${name}`} {...t}><PickLabel label="Type">{name}</PickLabel></Button>}>
        {(close) => (
          <>
            {formats.filter((f) => f.on && f.engine !== "song").map((f) => (
              <MenuItem key={f.id} onClick={() => { close(); if (f.id !== s.format) setAsking(f); }}>
                {f.name}{f.id === s.format ? " ✓" : ""}
              </MenuItem>
            ))}
          </>
        )}
      </Menu>
      {swap.isError && <p role="alert" className={errorClass}>{swap.error.message}</p>}
      {asking && (
        <Dialog title={ask(asking, s).title} cancelLabel="Not yet" actionLabel="Change" busy={swap.isPending} onCancel={() => setAsking(null)} onConfirm={() => { swap.mutate(asking); setAsking(null); }}>
          {ask(asking, s).body}
        </Dialog>
      )}
    </>
  );
}

/** The Director's narrator check on the Script step (ST0, N1): Advice only, never a block. */
export function FormatAdvice({ script: s }: { script: Script }) {
  const swap = useSwap(s);
  const [asking, setAsking] = useState(false);
  const narrated = useFormats().data?.find((f) => f.on && f.engine === "narrated");
  const v = s.versions.find((x) => x.slot === 0);
  if (!v || s.published) return null;
  if (narrated && s.kind === "story" && v.reads_narrated)
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm" role="status">
        <Mic size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
        <span className="min-w-0 flex-1">This reads as narrated. Make it {narrated.name}?</span>
        <Button variant="secondary" dense busy={swap.isPending} onClick={() => setAsking(true)}>Make it {narrated.name}</Button>
        {swap.isError && <p role="alert" className={`w-full ${errorClass}`}>{swap.error.message}</p>}
        {asking && (
          <Dialog title={ask(narrated, s).title} cancelLabel="Not yet" actionLabel="Change" busy={swap.isPending} onCancel={() => setAsking(false)} onConfirm={() => { swap.mutate(narrated); setAsking(false); }}>
            {ask(narrated, s).body}
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
