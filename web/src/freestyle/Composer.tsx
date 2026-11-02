import { useState } from "react";
import { Button, Select, TextArea, pressLabel } from "../components";
import { lookName, useLooks } from "../scripts/Looks";
import { useBrands } from "../shell/useBrands";
import { Tag } from "./Thread";
import { SHAPES, SOON, TYPES, typeName, useEstimate, useFreestyleActions, type Freestyle, type Settings } from "./useFreestyle";

/** A freestyle's settings in words, for the tags on its first message and the composer's read-only row. */
export function useSettingsWords() {
  const looks = useLooks().data;
  const brands = useBrands().data;
  return (s: Settings) => [typeName(s.type), lookName(looks, s.look), s.shape, brands?.find((b) => b.id === s.brand_id)?.name ?? "No brand"];
}

/** The box at the bottom. New: the pickers (Type, Style, Shape, Brand) and the script; after: a change, with the
 *  settings read-only. The estimate sits by the button. Enter sends, Shift+Enter makes a new line. */
export function Composer({ fs, owner, maker, onCreated }: { fs?: Freestyle; owner: boolean; maker: boolean; onCreated: (id: number) => void }) {
  const looks = (useLooks().data ?? []).filter((l) => l.on);
  const brands = useBrands().data ?? [];
  const words = useSettingsWords();
  const [picked, setPicked] = useState<Partial<Settings>>({});
  const [text, setText] = useState("");
  const actions = useFreestyleActions(fs?.id ?? null);
  const settings: Settings = fs ?? { type: "one_clip", look: looks[0]?.id ?? "", shape: "9:16", brand_id: null, ...picked };
  const firstText = fs?.thread.find((t) => t.kind === "message")?.text ?? text; // a change costs what a take of the script does
  const estimate = useEstimate(settings, firstText);
  const send = fs ? actions.change : actions.create;
  const pick = (p: Partial<Settings>) => setPicked({ ...picked, ...p });

  if (fs && !maker) return <p className="text-sm text-muted">Only whoever made this freestyle can change it.</p>;
  const empty = !text.trim() || !settings.look; // never before the looks have loaded
  const go = () => {
    if (empty || send.isPending) return;
    if (fs) actions.change.mutate(text.trim(), { onSuccess: () => setText("") });
    else actions.create.mutate({ ...settings, text: text.trim() }, { onSuccess: (out) => onCreated(out.id) });
  };
  return (
    <form
      aria-label={fs ? "Your change" : "Your freestyle"}
      className="space-y-3 rounded-lg border border-border-strong bg-surface p-3"
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      {fs ? (
        <div className="flex flex-wrap gap-1.5" aria-label="Settings">
          {words(fs).map((w) => (
            <Tag key={w}>{w}</Tag>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Select label="Type" value={settings.type} onChange={(e) => pick({ type: e.target.value as Settings["type"] })}>
            {TYPES.map((t) => (
              <option key={t.id} value={t.id} disabled={t.soon}>
                {t.name}
              </option>
            ))}
          </Select>
          <Select label="Style" value={settings.look} onChange={(e) => pick({ look: e.target.value })}>
            {looks.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </Select>
          <Select label="Shape" value={settings.shape} onChange={(e) => pick({ shape: e.target.value as Settings["shape"] })}>
            {SHAPES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
          <Select label="Brand" value={settings.brand_id ?? ""} onChange={(e) => pick({ brand_id: Number(e.target.value) || null })}>
            <option value="">None</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
          <p className="col-span-full text-sm text-muted">{SOON}</p>
        </div>
      )}
      <TextArea
        label={fs ? "Ask for a change" : "Paste a script, or describe the clip"}
        rows={fs ? 2 : 4}
        maxLength={fs ? 2000 : 5000}
        value={text}
        hint={owner ? undefined : "Each send goes to the owner first. Nothing is spent until they say yes."}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            go();
          }
        }}
      />
      <div className="flex flex-wrap items-center justify-end gap-3">
        {estimate.data !== undefined && <span className="text-sm tabular-nums text-muted">{pressLabel(estimate.data, "estimate")}</span>}
        <Button type="submit" busy={send.isPending} disabled={empty}>
          {owner ? "Send" : "Send for approval"}
        </Button>
      </div>
      {send.isError && (
        <p role="alert" className="text-sm text-danger">
          {send.error.message}
        </p>
      )}
    </form>
  );
}
