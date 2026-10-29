import { useState } from "react";
import { Ellipsis, Lock, Merge, Pencil, Plus, Users } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Banner, Badge, Button, Card, Dialog, EmptyState, Field, Menu, MenuItem, Panel, Select, Skeleton, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import type { Script } from "./useScript";
import { FindRoles } from "./FindRoles";
import { LockPanel } from "./LockPanel";
import { useBrandCharacters, useCast, useCastActions, useMergeRoles, type Slot } from "./useCast";
import { MergeRole, mergedText } from "../projects/MergeRole";
import { MaybeSame, MaybeSameBadge, pairId, type Pair } from "../projects/MaybeSame";
import { RoleFacts } from "../projects/RoleFacts";
import { useSheetPrice } from "../library/SheetPanel";
import { wholeCredits } from "../components/credits";

/** Step 5: the roles of the script, each with one locked look or none (made at Assets). Every role is optional. */
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
  const locked = slots.filter((s) => s.locked).length;
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
  const factsText = (s: Slot) => [s.facts?.age_range, s.facts?.gender, s.facts?.occupation].map((f) => f?.value).filter(Boolean).join(" · ");

  return (
    <div className="max-w-[820px] space-y-4">
      {cast.isError && <Banner title="Couldn't load the cast." action={<Button variant="secondary" onClick={() => void cast.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {cast.isPending && (
        <div className="space-y-2" aria-label="Loading">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}
      {cast.data && !readOnly && <FindRoles script={script} hasRoles={slots.length > 0} />}
      {cast.data && slots.length === 0 && (
        <EmptyState icon={Users} title="No roles yet." action={!readOnly ? <Button variant="secondary" onClick={() => setAdding(true)}>Add a role</Button> : undefined}>
          Everyone will be made at Assets. Add a role to lock one look for it in every version.
        </EmptyState>
      )}
      {slots.length > 0 && (
        <>
          <p className="text-sm text-muted">
            {slots.length} role{slots.length === 1 ? "" : "s"} · {locked} locked
          </p>
          <MaybeSame pairs={pairs} name={roleName} outlined={outlined} onMerge={mergePair} onDismiss={keepTwo} />
          <Card className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {slots.map((s) => (
                <li key={s.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:px-5">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-display text-md font-bold">{s.role}</h3>
                      <Badge>{s.kind}</Badge>
                      {pairsOf(s.id).slice(0, 1).map((p) => (
                        <MaybeSameBadge key={pairId(p)} other={roleName(p.a === s.id ? p.b : p.a)} onClick={() => showPair(p)} />
                      ))}
                      {!readOnly && (
                        <button type="button" aria-label={`Rename ${s.role}`} onClick={() => setRenaming(s)} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                          <Pencil size={16} strokeWidth={1.75} aria-hidden />
                        </button>
                      )}
                    </div>
                    <RoleFacts facts={s.facts} />
                    {s.description && <p className="line-clamp-2 text-sm text-muted">{s.description}</p>}
                    {appearsText(s.appears_in) && <p className="text-sm text-muted">{appearsText(s.appears_in)}</p>}
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    {s.locked ? (
                      <>
                        {s.sheet_file_id && <img src={fileUrl(s.sheet_file_id)} alt="" className="size-14 rounded-md border border-border object-cover" />}
                        <span className="text-sm">
                          <Badge icon={Lock}>Locked{nameOf(s.library_item_id) ? ` to ${nameOf(s.library_item_id)}` : ""}</Badge>
                          <span className="mt-1 block text-muted">Used as-is in every version.</span>
                        </span>
                        {!readOnly && (
                          <>
                            <Button variant="ghost" dense aria-label={`Change the look for ${s.role}`} onClick={() => setLocking(s)}>
                              Change
                            </Button>
                            <Button variant="ghost" dense aria-label={`Unlock ${s.role}`} busy={act.unlock.isPending} onClick={() => act.unlock.mutate(s.id)}>
                              Unlock
                            </Button>
                          </>
                        )}
                      </>
                    ) : (
                      <>
                        {/* An unlocked role gets its own look in every video made from this script, each paid for there (rule 7). */}
                        <span className="text-sm text-muted">Not locked: each video makes its own look{sheet !== undefined && ` (about ${wholeCredits(sheet)} credit${wholeCredits(sheet) === 1 ? "" : "s"} each)`}.</span>
                        {!readOnly && (
                          <Button variant="secondary" aria-label={`Lock ${s.role} to a look`} onClick={() => setLocking(s)}>
                            Lock to a look
                          </Button>
                        )}
                      </>
                    )}
                    {!readOnly && (
                      <Menu title={s.role} align="right" trigger={(t) => <button type="button" {...t} aria-label={`More for ${s.role}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2"><Ellipsis size={20} strokeWidth={1.75} aria-hidden /></button>}>
                        {(close) => (
                          <>
                          <MenuItem
                            disabled={slots.length < 2}
                            onClick={() => {
                              close();
                              setMerging({ slot: s });
                            }}
                          >
                            <Merge size={18} strokeWidth={1.75} aria-hidden />
                            Merge into…
                          </MenuItem>
                          {slots.length < 2 && <p className="px-3 pb-2 text-xs text-muted">There's no other role to merge into.</p>}
                          <MenuItem
                            danger
                            onClick={() => {
                              close();
                              setRemoving(s);
                            }}
                          >
                            Remove role
                          </MenuItem>
                          </>
                        )}
                      </Menu>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
      {!readOnly && slots.length > 0 && (
        <Button variant="ghost" icon={Plus} onClick={() => setAdding(true)}>
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
          They'll be made at Assets like a background person.
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
