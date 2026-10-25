import { useState } from "react";
import { Ellipsis, Lock, Pencil, Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { Banner, Badge, Button, Card, Dialog, EmptyState, Field, Menu, MenuItem, Panel, Skeleton, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useBrandCharacters, useCast, useCastActions, type Slot } from "./useCast";

/** Step 5: the roles of the script, each with one locked look or none (made at Assets). Every role is optional. */
export function CastStep({ scriptId, brandId, readOnly }: { scriptId: number; brandId: number; readOnly: boolean }) {
  const cast = useCast(scriptId);
  const chars = useBrandCharacters(brandId);
  const act = useCastActions(scriptId);
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [locking, setLocking] = useState<Slot | null>(null);
  const [renaming, setRenaming] = useState<Slot | null>(null);
  const [removing, setRemoving] = useState<Slot | null>(null);
  const slots = cast.data ?? [];
  const nameOf = (id: number | null) => chars.data?.find((c) => c.id === id)?.name;
  const locked = slots.filter((s) => s.locked).length;

  return (
    <div className="max-w-[820px] space-y-4">
      {cast.isError && <Banner title="Couldn't load the cast." action={<Button variant="secondary" onClick={() => void cast.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {cast.isPending && (
        <div className="space-y-2" aria-label="Loading">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}
      {cast.data && slots.length === 0 && (
        <EmptyState icon={Users} title="No roles yet." action={!readOnly ? <Button onClick={() => setAdding(true)}>Add a role</Button> : undefined}>
          Everyone will be made at Assets. Add a role to lock one look for it in every version.
        </EmptyState>
      )}
      {slots.length > 0 && (
        <>
          <p className="text-sm text-muted">
            {slots.length} role{slots.length === 1 ? "" : "s"} · {locked} locked
          </p>
          <Card className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {slots.map((s) => (
                <li key={s.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:px-5">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-display text-md font-bold">{s.role}</h3>
                      {!readOnly && (
                        <button type="button" aria-label={`Rename ${s.role}`} onClick={() => setRenaming(s)} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                          <Pencil size={16} strokeWidth={1.75} aria-hidden />
                        </button>
                      )}
                    </div>
                    {s.description && <p className="line-clamp-2 text-sm text-muted">{s.description}</p>}
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
                        <span className="text-sm text-muted">Made at Assets</span>
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
                          <MenuItem
                            danger
                            onClick={() => {
                              close();
                              setRemoving(s);
                            }}
                          >
                            Remove role
                          </MenuItem>
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
          initial={{ role: renaming.role, description: renaming.description }}
          busy={act.edit.isPending}
          error={act.edit.isError ? act.edit.error.message : null}
          onClose={() => setRenaming(null)}
          onSubmit={(v) => act.edit.mutate({ id: renaming.id, ...v }, { onSuccess: () => setRenaming(null) })}
        />
      )}
      {removing && (
        <Dialog title={`Remove ${removing.role} from the cast?`} cancelLabel="Keep" actionLabel="Remove" danger busy={act.remove.isPending} onCancel={() => setRemoving(null)} onConfirm={() => act.remove.mutate(removing.id, { onSuccess: () => setRemoving(null) })}>
          They'll be made at Assets like a background person.
        </Dialog>
      )}
      {locking && (
        <Panel title={`Lock ${locking.role} to a look`} onClose={() => setLocking(null)}>
          <div className="space-y-3">
            <p className="text-sm text-muted">Characters from Cast & places that have an approved sheet.</p>
            {chars.isPending && <Skeleton className="h-32" />}
            <ul className="grid grid-cols-2 gap-3">
              {(chars.data ?? []).map((c) => {
                const ready = c.sheet_status === "approved";
                return (
                  <li key={c.id} className="space-y-1">
                    <button
                      type="button"
                      disabled={!ready || act.lock.isPending}
                      aria-label={ready ? `Lock to ${c.name}` : `${c.name} needs an approved sheet`}
                      onClick={() =>
                        act.lock.mutate(
                          { id: locking.id, libraryItemId: c.id },
                          {
                            onSuccess: () => {
                              toast(`${locking.role} is locked. They'll look the same in every version.`);
                              setLocking(null);
                            },
                          },
                        )
                      }
                      className="relative block aspect-[9/16] w-full overflow-hidden rounded-lg border border-border bg-surface-2 disabled:opacity-60"
                    >
                      {c.image_file_ids?.[0] && <img src={fileUrl(c.image_file_ids[0])} alt="" className="size-full object-cover" />}
                      <span className="absolute inset-x-2 bottom-2 text-left font-display font-bold text-on-media drop-shadow">{c.name}</span>
                    </button>
                    {!ready && (
                      <p className="text-sm text-muted">
                        Needs an approved sheet.{" "}
                        <Link to={`/b/${brandId}/library/characters/${c.id}`} className="text-accent-text underline">
                          Open
                        </Link>
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
            {chars.data?.length === 0 && <p className="text-sm text-muted">This brand has no characters yet. Add them in Cast & places.</p>}
            {act.lock.isError && <p role="alert" className={errorClass}>{act.lock.error.message}</p>}
          </div>
        </Panel>
      )}
    </div>
  );
}

function RolePanel({ title, submit, initial, busy, error, onClose, onSubmit }: { title: string; submit: string; initial?: { role: string; description: string }; busy: boolean; error: string | null; onClose: () => void; onSubmit: (v: { role: string; description: string }) => void }) {
  const [role, setRole] = useState(initial?.role ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  return (
    <Panel title={title} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (role.trim()) onSubmit({ role: role.trim(), description: description.trim() });
        }}
      >
        <Field label="Role" placeholder="e.g. Mia" value={role} onChange={(e) => setRole(e.target.value)} />
        <TextArea label="Description" rows={3} placeholder="Late 20s, confident, says hell no at the altar." value={description} onChange={(e) => setDescription(e.target.value)} />
        {error && <p role="alert" className={errorClass}>{error}</p>}
        <Button type="submit" busy={busy} disabled={!role.trim()} className="w-full">
          {submit}
        </Button>
      </form>
    </Panel>
  );
}
