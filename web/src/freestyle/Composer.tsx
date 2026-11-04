import { useState, type KeyboardEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { ArrowUp, Lock } from "lucide-react";
import { Button, Menu, MenuItem } from "../components";
import { lookName, useLooks } from "../scripts/Looks";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { SHAPES, useEstimate, useFreestyleActions, useTypeName, useTypes, type Freestyle, type Settings, type Source } from "./useFreestyle";

/** A freestyle's settings in words, for the tags on its first message. */
export function useSettingsWords() {
  const looks = useLooks().data;
  const brands = useBrands().data;
  const typeName = useTypeName();
  return (s: Settings) => [typeName(s.type), lookName(looks, s.look), s.shape, brands?.find((b) => b.id === s.brand_id)?.name ?? "No brand"];
}

/** ⌘↵ (Ctrl+↵ off a Mac) sends from the box; a plain Enter is a new line (B_NewVideoReady). */
export const sendKey = (go: () => void) => (e: KeyboardEvent) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing) {
    e.preventDefault();
    go();
  }
};

const chip = "inline-flex min-h-control items-center gap-1.5 whitespace-nowrap rounded-md border border-border px-2.5 text-sm lg:min-h-control-dense lg:px-2 lg:text-xs"; // 12 px on desktop, as drawn

/** A setting as a chip, "Type Dialogue": a menu of its choices, or with `locked` a read-only chip with a lock (a script's
 *  own type, style and brand, E_PickInComposer). On a phone the chips fill a 2×2 grid. */
export function Pick<T extends string | number>({ label, value, options, onPick, locked }: { label: string; value: T; options?: { id: T; name: string; off?: string }[]; onPick?: (v: T) => void; locked?: boolean }) {
  const name = options?.find((o) => o.id === value)?.name ?? String(value);
  if (locked || !options || !onPick)
    return (
      <span className={`${chip} text-muted`} aria-label={`${label}: ${name}, from the script`}>
        <Lock size={12} strokeWidth={1.75} aria-hidden />
        {label} <span className="text-text">{name}</span>
      </span>
    );
  return (
    <Menu
      title={label}
      trigger={(p) => (
        <button type="button" {...p} aria-label={`${label}: ${name}`} className={`${chip} w-full hover:bg-surface-2 lg:w-auto`}>
          <span className="text-muted">{label}</span>
          {name}
        </button>
      )}
    >
      {(close) =>
        options.map((o) => (
          <MenuItem
            key={String(o.id)}
            checked={o.id === value}
            disabled={!!o.off}
            onClick={() => {
              close();
              onPick(o.id);
            }}
          >
            <span className="flex-1">{o.name}</span>
            {o.off && <span className="text-sm text-muted">{o.off}</span>}
          </MenuItem>
        ))
      }
    </Menu>
  );
}

export const shapeOptions = SHAPES.map((s) => ({ id: s, name: s }));

/** The one press of New video and Make a video: the owner's makes it at once, an editor's goes to the owner; both carry
 *  their cap ("up to N credits", rule 34) once it's known, and ⌘↵. */
export function SendPress({ owner, price, busy, disabled, wide, onClick }: { owner: boolean; price: number | undefined; busy: boolean; disabled: boolean; wide?: boolean; onClick?: () => void }) {
  return (
    <Button type={onClick ? "button" : "submit"} busy={busy} disabled={disabled} kbd={wide ? undefined : "⌘↵"} onClick={onClick} className={wide ? "w-full" : "shrink-0 whitespace-nowrap lg:px-3 lg:text-sm"} price={disabled ? undefined : price} charge="estimate">
      {owner ? "Make it" : "Send for approval"}
    </Button>
  );
}

/** New video's box (B_NewVideo): the words in the script font, the settings as chips under them and the press on the
 *  right. The brand starts as the rail's. */
export function Composer({ brandId, owner, onCreated, below }: { brandId: number; owner: boolean; onCreated: (fs: Freestyle) => void; below: (typed: boolean) => ReactNode }) {
  const looks = (useLooks().data ?? []).filter((l) => l.on);
  const brands = useBrands().data ?? [];
  const types = useTypes();
  const [picked, setPicked] = useState<Partial<Settings>>({});
  const [text, setText] = useState("");
  const create = useFreestyleActions(null).create;
  const rail = useRail();
  const settings: Settings = { type: "dialogue", look: looks[0]?.id ?? "", shape: "9:16", brand_id: brandId, ...picked };
  const source: Source = { text, settings };
  const estimate = useEstimate(source);
  const pick = (p: Partial<Settings>) => setPicked({ ...picked, ...p });
  const empty = !text.trim() || !settings.look; // never before the looks have loaded
  const go = () => !empty && !create.isPending && create.mutate({ text: text.trim(), settings }, { onSuccess: onCreated });
  const chips = (
    <div className="grid grid-cols-2 gap-2 lg:flex lg:gap-1.5">
      <Pick label="Type" value={settings.type} options={types.map((t) => ({ id: t.id, name: t.name, off: t.soon ? "coming next" : undefined }))} onPick={(type) => pick({ type })} />
      <Pick label="Style" value={settings.look} options={looks.map((l) => ({ id: l.id, name: l.name }))} onPick={(look) => pick({ look })} />
      <Pick label="Brand" value={settings.brand_id ?? 0} options={[...brands.map((b) => ({ id: b.id, name: b.name })), { id: 0, name: "None" }]} onPick={(b) => pick({ brand_id: b || null })} />
      <Pick label="Shape" value={settings.shape} options={shapeOptions} onPick={(shape) => pick({ shape })} />
    </div>
  );
  return (
    <form
      aria-label="New video"
      className="space-y-3 lg:space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      <div className="flex flex-col gap-3 rounded-lg border border-border-strong bg-surface p-3.5 focus-within:border-focus">
        <label htmlFor="new-video-words" className="sr-only">
          Paste a script, or describe the video
        </label>
        <textarea
          id="new-video-words"
          autoFocus={rail} // a keyboard starts typing at once; a phone keeps its keyboard down until tapped
          rows={8}
          maxLength={5000}
          value={text}
          placeholder="Paste a script, or describe the video"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={sendKey(go)}
          className="min-h-[180px] resize-none bg-transparent font-script text-base text-text outline-none! placeholder:text-faint lg:text-script"
        />
        {rail && (
          <div className="flex items-center justify-between gap-3">
            {chips}
            <SendPress owner={owner} price={estimate.data} busy={create.isPending} disabled={empty} />
          </div>
        )}
      </div>
      {!rail && chips /* a phone: a 2×2 grid under the box (B_PhoneNew) */}
      {create.isError && (
        <p role="alert" className="text-sm text-danger">
          {create.error.message}
        </p>
      )}
      {below(!empty)}
      {!rail && (
        <ActionBar phone>
          <SendPress owner={owner} price={estimate.data} busy={create.isPending} disabled={empty} wide onClick={go} />
        </ActionBar>
      )}
    </form>
  );
}

/** The owner's note on a finished video is saved for Make it again (a note never starts a run by itself, the Producer). */
function useSaveNote(projectId: number | undefined, freestyleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: projectId ?? 0 } }, body: { text } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", projectId], data);
      return queryClient.invalidateQueries({ queryKey: ["freestyle", freestyleId] });
    },
  });
}

/** The change box under a thread (B_VideoRunning): "Tell the director what to change", the status line under it and the
 *  send arrow. Enter sends, Shift+Enter is a new line. An editor's change goes to the owner; `saveTo` (the owner, nothing
 *  running): saved on that video for Make it again. `closed`: one quiet line saying when it opens (E_EditorSent);
 *  `disabled`: the box, greyed, with the status line saying why (B_VideoWaiting). */
export function ChangeBox({ fs, status, closed, disabled, saveTo }: { fs: Freestyle; status: ReactNode; closed?: string | null; disabled?: boolean; saveTo?: number }) {
  const [text, setText] = useState("");
  const asked = useFreestyleActions(fs.id).change;
  const saved = useSaveNote(saveTo, fs.id);
  const change = saveTo ? saved : asked;
  const go = () => text.trim() && !change.isPending && !closed && !disabled && change.mutate(text.trim(), { onSuccess: () => setText("") });
  const rail = useRail();
  if (closed)
    return (
      <p className="flex min-h-control items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm text-muted">
        <span>Tell the director what to change</span>
        <span>{closed}</span>
      </p>
    );
  const said = (
    <p className="text-sm text-muted" role="status">
      {change.isError ? <span className="text-danger">{change.error.message}</span> : status}
    </p>
  );
  const send = <Button type="submit" variant="secondary" dense icon={ArrowUp} busy={change.isPending} disabled={!text.trim() || disabled} aria-label="Send the change" />;
  // On a phone (B_PhoneVideo): the line above, then a one-line box with the send beside it.
  return (
    <form
      aria-label="Your change"
      className={rail ? "flex flex-col gap-2 rounded-lg border border-border-strong bg-surface p-3 focus-within:border-focus" : "space-y-2"}
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      {!rail && said}
      <label htmlFor={`change-${fs.id}`} className="sr-only">
        Tell the director what to change
      </label>
      <div className={rail ? "contents" : "flex items-center gap-2"}>
      <textarea
        id={`change-${fs.id}`}
        rows={rail ? 2 : 1}
        maxLength={2000}
        value={text}
        disabled={disabled}
        placeholder="Tell the director what to change"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            go();
          }
        }}
        className={rail ? "min-h-10 resize-none bg-transparent px-0.5 text-base outline-none! placeholder:text-faint" : "min-h-control min-w-0 flex-1 resize-none rounded-md border border-border-strong bg-surface px-3 py-2.5 text-base placeholder:text-faint"}
      />
      {!rail && send}
      </div>
      {rail && (
        <div className="flex items-center justify-between gap-3">
          {said}
          {send}
        </div>
      )}
    </form>
  );
}
