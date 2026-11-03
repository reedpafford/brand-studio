import { useState } from "react";
import { Ellipsis, Lock, Merge, Pencil, Plus, Users } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Banner, Button, Dialog, EmptyState, Field, Menu, MenuItem, Panel, Select, Skeleton, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import type { Script } from "./useScript";
import { FindRoles } from "./FindRoles";
import { SingerCard } from "./SongParts";
import { LockPanel } from "./LockPanel";
import { useBrandCharacters, useCast, useCastActions, useMergeRoles, type Slot } from "./useCast";
import { RoleFacts } from "../projects/RoleFacts";
import { MergeRole, mergedText } from "../projects/MergeRole";
import { MaybeSame, MaybeSameBadge, pairId, type Pair } from "../projects/MaybeSame";
import { useSheetPrice } from "../library/SheetPanel";
import { wholeCredits } from "../components/credits";

/** Step 5: the roles of the script, each with one locked look or none (made in the video's Cast). Every role is optional. */
export function CastStep({ script, brandId, readOnly }: { script: Script; brandId: number; readOnly: boolean }) {
  const scriptId = script.id;
  const cast = useCast(scriptId);
  const chars = useBrandCharacters(brandId);
  const act = useCastActions(scriptId);
  const toast = useToast();
  const sheet = useSheetPrice().price;
  const [adding, setAdding] = useState(false);
  const [locking, setLocking] = useState<Slot | null>(null);
  const [renaming, setRenaming] = useState<Slot | null>(null);
  const [removing, setRemoving] = useState<Slot | null>(null);
  const [merging, setMerging] = useState<{ slot: Slot; suggested?: number } | null>(null);
  const [outlined, setOutlined] = useState<string | null>(null);
  const roles = useMergeRoles(scriptId);
  const slots = cast.data ?? [];
  const nameOf = (id: number | null) => chars.data?.find((c) => c.id === id)?.name;
  const roleName = (id: number) => slots.find((x) => x.id === id)?.role ?? "";
  // The server's "may be the same person" flags; both roles must still be here.
  const pairs: Pair[] = readOnly ? [] : (script.maybe_same ?? []).filter((p) => slots.some((x) => x.id === p.a_slot_id) && slots.some((x) => x.id === p.b_slot_id)).map((p) => ({ a: p.a_slot_id, b: p.b_slot_id, into: p.into_slot_id, why: p.why }));
  const pairsOf = (id: number) => pairs.filter((p) => p.a === id || p.b === id);
  const showPair = (p: Pair) => {
    document.getElementById(pairId(p))?.scrollIntoView?.({ block: "center" });
    setOutlined(pairId(p));
    setTimeout(() => setOutlined(null), 1500);
  };
  const mergePair = (p: Pair) => {
    const slot = slots.find((x) => x.id === (p.into === p.a ? p.b : p.a));
    if (slot) setMerging({ slot, suggested: p.into });
  };
  const keepTwo = (p: Pair) =>
    void roles.dismiss(p.a, p.b).then(
      () => toast("Kept as two roles.", () => void roles.undoDismiss(p.a, p.b).catch((e: Error) => toast(e.message, undefined, "error"))),
      (e: Error) => toast(e.message, undefined, "error"),
    );
  /** A role's status: a dot and words ("Not locked" carries what an own look costs, on hover). */
  const status = (s: Slot) => (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted sm:w-44" title={!s.locked && sheet !== undefined ? `Each video makes its own look (about ${wholeCredits(sheet)} credit${wholeCredits(sheet) === 1 ? "" : "s"} each).` : undefined}>
      <span aria-hidden className={`size-2 rounded-full ${s.locked ? "bg-success" : "bg-warning"}`} />
      {s.locked ? `Locked${nameOf(s.library_item_id) ? ` to ${nameOf(s.library_item_id)}` : ""}` : "Not locked"}
    </span>
  );
  const factsText = (s: Slot) => [s.facts?.age_range, s.facts?.gender, s.facts?.occupation].map((f) => f?.value).filter(Boolean).join(" · ");

  return (
    <div className="max-w-[820px] space-y-4">
      {script.kind === "song" && <SingerCard script={script} />}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div>
          <h2 className="text-sm font-semibold">Cast</h2>
          <p className="text-sm text-muted">Lock each role to a character, so every clip uses the same face and outfit.</p>
        </div>
        {cast.data && !readOnly && slots.length > 0 && <FindRoles script={script} hasRoles />}
      </div>
      {cast.isError && <Banner title="Couldn't load the cast." action={<Button variant="secondary" onClick={() => void cast.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {cast.isPending && (
        <div className="space-y-2" aria-label="Loading">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      )}
      {cast.data && !readOnly && slots.length === 0 && <FindRoles script={script} hasRoles={false} />}
      {cast.data && slots.length === 0 && (
        <EmptyState icon={Users} title="No roles yet." action={!readOnly ? <Button variant="secondary" onClick={() => setAdding(true)}>Add a role</Button> : undefined}>
          Everyone will be made in the video's Cast. Add a role to lock one look for it in every version.
        </EmptyState>
      )}
      {slots.length > 0 && (
        <>
          <MaybeSame pairs={pairs} name={roleName} outlined={outlined} onMerge={mergePair} onDismiss={keepTwo} />
          {/* v5 C_CastLock: one 64 px row per role: picture, name over where it appears, a status dot, and the one press. */}
          <ul className="divide-y divide-border border-y border-border">
            {slots.map((s) => {
              const where = appearsText(s.appears_in);
              return (
                <li key={s.id} className="flex min-h-16 flex-wrap items-center gap-x-3 gap-y-1 py-2">
                  <span aria-hidden className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-surface-2 text-muted">
                    {s.locked && s.sheet_file_id ? <img src={fileUrl(s.sheet_file_id)} alt="" className="size-full object-cover" /> : <Users size={16} strokeWidth={1.75} />}
                  </span>
                  <div className="min-w-[9rem] flex-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <h3 className="truncate text-sm font-medium">{s.role}</h3>
                      {pairsOf(s.id).slice(0, 1).map((p) => (
                        <MaybeSameBadge key={pairId(p)} other={roleName(p.a === s.id ? p.b : p.a)} onClick={() => showPair(p)} />
                      ))}
                    </div>
                    <RoleFacts facts={s.facts} className="truncate text-xs text-muted" />
                    {where && <p className="truncate text-xs text-muted">{where}</p>}
                  </div>
                  {/* An unlocked role gets its own look in every video made from this script, each paid for there (rule 7). */}
                  {status(s)}
                  {!readOnly && (
                    <Button variant="secondary" dense aria-label={s.locked ? `Change the look for ${s.role}` : `Lock ${s.role} to a look`} onClick={() => setLocking(s)}>
                      {s.locked ? "Change" : "Lock to a look"}
                    </Button>
                  )}
                  {!readOnly && (
                    <Menu title={s.role} align="right" trigger={(t) => <button type="button" {...t} aria-label={`More for ${s.role}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2"><Ellipsis size={20} strokeWidth={1.75} aria-hidden /></button>}>
                      {(close) => (
                        <>
                          <MenuItem onClick={() => { close(); setRenaming(s); }}>
                            <Pencil size={18} strokeWidth={1.75} aria-hidden />
                            Rename
                          </MenuItem>
                          {s.locked && (
                            <MenuItem onClick={() => { close(); act.unlock.mutate(s.id); }}>
                              <Lock size={18} strokeWidth={1.75} aria-hidden />
                              Unlock
                            </MenuItem>
                          )}
                          <MenuItem disabled={slots.length < 2} onClick={() => { close(); setMerging({ slot: s }); }}>
                            <Merge size={18} strokeWidth={1.75} aria-hidden />
                            Merge into…
                          </MenuItem>
                          {slots.length < 2 && <p className="px-3 pb-2 text-xs text-muted">There's no other role to merge into.</p>}
                          <MenuItem danger onClick={() => { close(); setRemoving(s); }}>
                            Remove role
                          </MenuItem>
                        </>
                      )}
                    </Menu>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
      {!readOnly && slots.length > 0 && (
        <Button variant="ghost" dense icon={Plus} onClick={() => setAdding(true)}>
          Add a role
        </Button>
      )}
      {adding && <RolePanel title="Add a role" submit="Add role" busy={act.add.isPending} error={act.add.isError ? act.add.error.message : null} onClose={() => setAdding(false)} onSubmit={(v) => act.add.mutate(v, { onSuccess: () => setAdding(false) })} />}
      {renaming && (
        <RolePanel
          title={`Rename ${renaming.role}`}
          submit="Save role"
          initial={{ role: renaming.role, kind: (KINDS.find((k) => k === renaming.kind) ?? "Main"), description: renaming.description }}
          busy={act.edit.isPending}
          error={act.edit.isError ? act.edit.error.message : null}
          onClose={() => setRenaming(null)}
          onSubmit={(v) => act.edit.mutate({ id: renaming.id, ...v }, { onSuccess: () => setRenaming(null) })}
        />
      )}
      {merging && (
        <MergeRole
          role={merging.slot.role}
          roleId={merging.slot.id}
          others={slots.filter((x) => x.id !== merging.slot.id).map((x) => ({ id: x.id, role: x.role, kind: x.kind, locked: x.locked, facts: factsText(x) }))}
          suggested={merging.suggested}
          adapter={{ preview: (into) => roles.preview(merging.slot.id, into), merge: async (into) => {
            const r = await roles.merge(merging.slot.id, into);
            return { ...r.moved, token: r.token };
          } }}
          onMerged={(into, merged) => {
            setMerging(null);
            toast(mergedText(into.role, merged), () => void roles.undoMerge(merged.token!).catch((e: Error) => toast(e.message, undefined, "error")));
          }}
          onClose={() => setMerging(null)}
        />
      )}
      {removing && (
        <Dialog title={`Remove ${removing.role} from the cast?`} cancelLabel="Keep" actionLabel="Remove" danger busy={act.remove.isPending} onCancel={() => setRemoving(null)} onConfirm={() => act.remove.mutate(removing.id, { onSuccess: () => setRemoving(null) })}>
          They'll be made in the video's Cast like a background person.
        </Dialog>
      )}
      {locking && (
        <LockPanel
          slot={locking}
          brandId={brandId}
          locking={act.lock.isPending}
          onClose={() => setLocking(null)}
          onLock={(itemId) =>
            act.lock.mutate(
              { id: locking.id, libraryItemId: itemId },
              {
                onSuccess: () => {
                  toast(`${locking.role} is locked. They'll look the same in every version.`);
                  setLocking(null);
                },
              },
            )
          }
        />
      )}
    </div>
  );
}

const KINDS = ["Main", "Helper", "Rival", "Family"] as const;
type Kind = (typeof KINDS)[number];
type RoleForm = { role: string; kind: Kind; description: string };
const LETTERS = ["A", "B", "C"];
/** "In A, B and C" from the slots of the versions a role appears in. */
const appearsText = (slots: number[]) => {
  const l = slots.map((n) => LETTERS[n]).filter(Boolean);
  return l.length === 0 ? "" : `In ${l.length === 1 ? l[0] : `${l.slice(0, -1).join(", ")} and ${l[l.length - 1]}`}`;
};

function RolePanel({ title, submit, initial, busy, error, onClose, onSubmit }: { title: string; submit: string; initial?: RoleForm; busy: boolean; error: string | null; onClose: () => void; onSubmit: (v: RoleForm) => void }) {
  const [role, setRole] = useState(initial?.role ?? "");
  const [kind, setKind] = useState<Kind>(initial?.kind ?? "Main");
  const [description, setDescription] = useState(initial?.description ?? "");
  return (
    <Panel title={title} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (role.trim()) onSubmit({ role: role.trim(), kind, description: description.trim() });
        }}
      >
        <Field label="Role" placeholder="e.g. Mia" value={role} onChange={(e) => setRole(e.target.value)} />
        <Select label="Kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          {KINDS.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </Select>
        <TextArea label="Description" rows={3} placeholder="Late 20s, confident, says hell no at the altar." value={description} onChange={(e) => setDescription(e.target.value)} />
        {error && <p role="alert" className={errorClass}>{error}</p>}
        <Button type="submit" busy={busy} disabled={!role.trim()} className="w-full">
          {submit}
        </Button>
      </form>
    </Panel>
  );
}
