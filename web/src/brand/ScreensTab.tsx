import { useMemo, useState } from "react";
import { Plus, Smartphone } from "lucide-react";
import { useParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { Banner, Button, EmptyState, Field, MediaCard, Select, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction } from "./BrandPage";
import { NAME_TAKEN, Panel, ScreenEditor, useAddScreen, useDeletedScreens, useRestoreScreen, useScreens, type Screen } from "./screens";

/** The brand's real screens as 9:16 tiles. Tags show in the editor, not on the tile. */
export function ScreensTab() {
  const brandId = Number(useParams().brandId);
  const screens = useScreens(brandId);
  const [editing, setEditing] = useState<Screen | null>(null);
  const [adding, setAdding] = useState(false);
  const [tag, setTag] = useState("");
  const [showDeleted, setShowDeleted] = useState(false);
  const deleted = useDeletedScreens(brandId);
  const restore = useRestoreScreen(brandId);
  const list = screens.data;
  const tags = [...new Set(list?.flatMap((s) => s.tags) ?? [])].sort();
  const shown = (list ?? []).filter((s) => !tag || s.tags.includes(tag));
  const addButton = (
    <Button icon={Plus} onClick={() => setAdding(true)}>Add screens</Button>
  );
  return (
    <div className="space-y-4">
      <BrandAction>{addButton}</BrandAction>
      {screens.isError && <Banner title="Couldn't load the app screens." action={<Button variant="secondary" onClick={() => void screens.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {screens.isPending && (
        <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="aspect-[9/19.5] rounded-lg" />
          ))}
        </div>
      )}
      {list?.length === 0 && (
        <EmptyState icon={Smartphone} title="No brand screens yet." action={addButton}>
          Add real app screens so videos show them exactly.
        </EmptyState>
      )}
      {list && list.length > 0 && (
        <>
          {/* v5 F_BrandScreens: the tag filter, then 9:16 tiles with the name and tag under each. */}
          <h2 className="sr-only">App screens · {list.length}</h2>
          {tags.length > 0 && (
            <div className="flex">
              <div className="w-48">
                <Select label="Tag" hideLabel value={tag} onChange={(e) => setTag(e.target.value)}>
                  <option value="">All tags</option>
                  {tags.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          )}
          {/* v5 F_BrandScreens: phone screenshots at 9:19.5, six to a row in a 900 px area (about 137 × 297). */}
          <ul className="grid max-w-[900px] grid-cols-3 gap-3 lg:grid-cols-6">
            {shown.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => setEditing(s)} className="block w-full space-y-1 text-left">
                  <span className="block aspect-[9/19.5] overflow-hidden rounded-lg bg-surface-2 hover:opacity-90">
                    <img src={fileUrl(s.file_id)} alt="" className="size-full object-cover" />
                  </span>
                  <span className="block truncate text-sm">{s.name}</span>
                </button>
                {(s.tags.length > 0 || s.default_for.length > 0) && (
                  <p className="truncate text-xs text-muted">
                    {[...s.tags, s.default_for.length > 0 && `${s.default_for[0].replace(/[-_]+/g, " ")}${s.default_for.length > 1 ? ` +${s.default_for.length - 1}` : ""}`].filter(Boolean).join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {(deleted.data?.length ?? 0) > 0 && (
        <div className="space-y-3">
          <Button variant="ghost" aria-expanded={showDeleted} onClick={() => setShowDeleted(!showDeleted)}>
            {showDeleted ? "Hide deleted" : `Show deleted (${deleted.data?.length})`}
          </Button>
          {showDeleted && (
            <ul className="grid grid-cols-3 gap-3 lg:grid-cols-6" aria-label="Deleted screens">
              {deleted.data?.map((s) => (
                <li key={s.id} className="space-y-2 opacity-60">
                  <MediaCard title={s.name} aspect="9 / 16" image={fileUrl(s.file_id)} icon={Smartphone} />
                  <p className="text-sm text-muted">Deleted</p>
                  <Button variant="secondary" dense className="w-full" aria-label={`Restore ${s.name}`} onClick={() => void restore(s)}>
                    Restore
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {editing && <ScreenEditor key={editing.id} brandId={brandId} screen={editing} onClose={() => setEditing(null)} />}
      {adding && <AddScreens brandId={brandId} tags={tags} onClose={() => setAdding(false)} />}
    </div>
  );
}

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

/** A drop zone that takes several pictures; each becomes a screen, named from its file. */
function AddScreens({ brandId, tags, onClose }: { brandId: number; tags: string[]; onClose: () => void }) {
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
        await add.mutateAsync({ file: p.file, name: p.name, tags: p.tag ? [p.tag] : [] });
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
