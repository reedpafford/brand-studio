import { useState } from "react";
import { Smartphone, Upload } from "lucide-react";
import { useParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, EmptyState, Field, MediaCard, Select, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction } from "./BrandPage";
import { Panel, ScreenEditor, useAddScreen, useScreens, type Screen } from "./screens";

/** The brand's real screens as 9:16 tiles. Tags show in the editor, not on the tile. */
export function ScreensTab() {
  const brandId = Number(useParams().brandId);
  const screens = useScreens(brandId);
  const [editing, setEditing] = useState<Screen | null>(null);
  const [adding, setAdding] = useState(false);
  const [tag, setTag] = useState("");
  const list = screens.data;
  const tags = [...new Set(list?.flatMap((s) => s.tags) ?? [])].sort();
  const shown = (list ?? []).filter((s) => !tag || s.tags.includes(tag));
  const addButton = (
    <Button onClick={() => setAdding(true)}>Add screens</Button>
  );
  return (
    <div className="space-y-4">
      <BrandAction>{addButton}</BrandAction>
      {screens.isError && <Banner title="Couldn't load the app screens." action={<Button variant="secondary" onClick={() => void screens.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {screens.isPending && (
        <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="aspect-[9/16] rounded-lg" />
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
          <div className="flex items-end justify-between gap-3">
            <h2 className="type-section">
              App screens <span className="text-muted">· {list.length}</span>
            </h2>
            {tags.length > 0 && (
              <div className="w-48">
                <Select label="Tag" value={tag} onChange={(e) => setTag(e.target.value)}>
                  <option value="">All tags</option>
                  {tags.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </div>
          <ul className="grid grid-cols-3 gap-3 lg:grid-cols-6">
            {shown.map((s) => (
              <li key={s.id}>
                <MediaCard
                  title={s.name}
                  aspect="9 / 16"
                  image={fileUrl(s.file_id)}
                  icon={Smartphone}
                  onOpen={() => setEditing(s)}
                  badge={s.default_for.length > 0 ? <Badge tone="media" icon={Smartphone}><span className="sr-only lg:not-sr-only">{s.default_for[0].replace(/[-_]+/g, " ")}{s.default_for.length > 1 && ` +${s.default_for.length - 1}`}</span></Badge> : undefined}
                />
              </li>
            ))}
          </ul>
        </>
      )}
      {editing && <ScreenEditor key={editing.id} brandId={brandId} screen={editing} onClose={() => setEditing(null)} />}
      {adding && <AddScreens brandId={brandId} onClose={() => setAdding(false)} />}
    </div>
  );
}

type Pick = { file: File; name: string; error?: string };

/** A drop zone that takes several pictures; each becomes a screen, named from its file. */
function AddScreens({ brandId, onClose }: { brandId: number; onClose: () => void }) {
  const toast = useToast();
  const add = useAddScreen(brandId);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [busy, setBusy] = useState(false);
  const take = (files: FileList | null) => {
    if (!files) return;
    setPicks([...picks, ...[...files].map((file) => ({ file, name: file.name.replace(/\.[^.]+$/, "") }))]);
  };
  const run = async () => {
    setBusy(true);
    const left: Pick[] = [];
    let made = 0;
    for (const p of picks) {
      try {
        await add.mutateAsync({ file: p.file, name: p.name });
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
    <Panel title="Add screens" onClose={onClose}>
      <div className="space-y-4">
        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border-strong bg-surface-2 p-4 text-center text-sm text-muted focus-within:outline focus-within:outline-2 focus-within:outline-accent">
          <Upload size={24} strokeWidth={1.75} aria-hidden />
          <span className="font-medium text-text">Choose pictures</span>
          <span>PNG, JPG or WebP. You can pick several.</span>
          <input type="file" accept="image/*" multiple className="sr-only" aria-label="Screen images" onChange={(e) => take(e.target.files)} />
        </label>
        {picks.length > 0 && (
          <ul className="space-y-3">
            {picks.map((p, i) => (
              <li key={`${p.file.name}-${i}`} className="space-y-1">
                <Field label={`Name for ${p.file.name}`} value={p.name} onChange={(e) => setPicks(picks.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} error={p.error} />
              </li>
            ))}
          </ul>
        )}
        {add.isError && !busy && picks.length === 0 && <p role="alert" className={errorClass}>{add.error.message}</p>}
        <Button className="w-full" busy={busy} disabled={picks.length === 0 || picks.some((p) => !p.name.trim())} onClick={() => void run()}>
          {picks.length > 1 ? `Add ${picks.length} screens` : "Add screen"}
        </Button>
      </div>
    </Panel>
  );
}
