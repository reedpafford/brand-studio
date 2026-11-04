import { useMemo, useState } from "react";
import { Button, Field, Select } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { NAME_TAKEN, Panel, useAddScreen, useDeletedScreens, useRestoreScreen } from "./screens";

type Pick = { file: File; name: string; tag: string; error?: string };

/** "order-tracking.png" reads "Order tracking". */
const readable = (file: string) => {
  const words = file.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** A picked file's own picture, for as long as it is picked. */
function Thumb({ file }: { file: File }) {
  // The picture's address is let go once it has drawn; the drawn picture stays.
  const url = useMemo(() => (typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null), [file]);
  return <span className="block h-20 w-11 shrink-0 overflow-hidden rounded-md bg-surface-2">{url && <img src={url} alt="" onLoad={() => URL.revokeObjectURL(url)} className="size-full object-cover" />}</span>;
}

/** A drop zone that takes several pictures; each becomes one of the product's screens, named from its file (an app's
 *  screens, S-gaps-05 L1). */
export function AddScreens({ brandId, productId, tags, onClose }: { brandId: number; productId: number; tags: string[]; onClose: () => void }) {
  const toast = useToast();
  const add = useAddScreen(brandId);
  const deleted = useDeletedScreens(brandId);
  const restore = useRestoreScreen(brandId);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [busy, setBusy] = useState(false);
  const take = (files: FileList | null) => {
    if (!files) return;
    setPicks([...picks, ...[...files].map((file) => ({ file, name: readable(file.name), tag: "" }))]);
  };
  const run = async () => {
    setBusy(true);
    const left: Pick[] = [];
    let made = 0;
    for (const p of picks) {
      try {
        await add.mutateAsync({ file: p.file, name: p.name, tags: p.tag ? [p.tag] : [], productId });
        made += 1;
      } catch (e) {
        left.push({ ...p, error: e instanceof Error ? e.message : "That didn't upload." });
      }
    }
    setBusy(false);
    setPicks(left);
    if (made > 0) toast(made === 1 ? "Screen added." : `${made} screens added.`);
    if (left.length === 0) onClose();
  };
  return (
    // v5 F_BrandScreens: a dashed area with an outlined Choose pictures; each picked file with its picture, name and tag;
    // Cancel and Add N screens pinned in the panel's footer.
    <Panel
      wide
      title="Add screens"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button busy={busy} disabled={picks.length === 0 || picks.some((p) => !p.name.trim())} onClick={() => void run()}>
            {picks.length > 1 ? `Add ${picks.length} screens` : "Add screen"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-strong p-4 text-center text-sm text-muted focus-within:outline focus-within:outline-2 focus-within:outline-accent">
          <span className="inline-flex min-h-control items-center rounded-md border border-border-button px-3 font-medium text-text hover:bg-surface-2 lg:min-h-control-dense">Choose pictures</span>
          <span>PNG, JPG or WebP. You can pick several.</span>
          <input type="file" accept="image/*" multiple className="sr-only" aria-label="Screen images" onChange={(e) => take(e.target.files)} />
        </label>
        {picks.length > 0 && (
          <ul className="space-y-3">
            {picks.map((p, i) => (
              <li key={`${p.file.name}-${i}`} className="flex gap-3">
                <Thumb file={p.file} />
                <div className="min-w-0 flex-1 space-y-2">
                <Field label={`Name for ${p.file.name}`} hideLabel value={p.name} onChange={(e) => setPicks(picks.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} error={p.error} />
                {tags.length > 0 && (
                  <Select label={`Tag for ${p.file.name}`} hideLabel value={p.tag} onChange={(e) => setPicks(picks.map((x, j) => (j === i ? { ...x, tag: e.target.value } : x)))}>
                    <option value="">No tag</option>
                    {tags.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </Select>
                )}
                {p.error?.startsWith(NAME_TAKEN) &&
                  (() => {
                    const clash = deleted.data?.find((d) => d.name.trim().toLowerCase() === p.name.trim().toLowerCase());
                    return clash ? (
                      <Button variant="ghost" onClick={() => void restore(clash).then(() => setPicks(picks.filter((_, j) => j !== i)))}>
                        Restore "{clash.name}"
                      </Button>
                    ) : null;
                  })()}
                </div>
              </li>
            ))}
          </ul>
        )}
        {add.isError && !busy && picks.length === 0 && <p role="alert" className={errorClass}>{add.error.message}</p>}
      </div>
    </Panel>
  );
}
