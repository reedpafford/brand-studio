import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Palette } from "lucide-react";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Button, Card, Panel, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** A look: how the pictures are drawn (flows ST1; Next-Server's GET /looks, #873). House first, then Reed's order. */
export type Look = components["schemas"]["LookOut"];

/** The looks, or null where the server doesn't offer them (the pickers stay hidden: never a press with nothing behind it). */
export function useLooks() {
  return useQuery({
    queryKey: ["looks"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/looks");
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(errorText(error));
      return data ?? null;
    },
    staleTime: 60_000,
  });
}

/** The picker: one card per look with its sample still, name and line. Off looks are greyed for editors; the owner may try one on their own work. */
export function LookPicker({ current, looks, onPick, busy, error, onClose }: { current: string; looks: Look[]; onPick: (l: Look) => void; busy: string | null; error: string | null; onClose: () => void }) {
  const owner = useMe().data?.role === "owner";
  return (
    <Panel title="Look" onClose={onClose}>
      <p className="mb-3 text-sm text-muted">How the pictures are drawn. Any look goes with any format.</p>
      {error && <p role="alert" className={`mb-3 ${errorClass}`}>{error}</p>}
      <ul className="grid gap-3 sm:grid-cols-2 [&>li]:min-w-0">
        {looks.map((l) => {
          const inUse = l.id === current;
          const closed = !l.on && !owner;
          return (
            <li key={l.id}>
              <Card className={`h-full space-y-2 ${closed ? "opacity-60" : ""}`}>
                <div className="grid aspect-[9/16] max-h-64 w-full place-items-center overflow-hidden rounded-md bg-surface-2">
                  {l.sample_still_id ? <img src={fileUrl(l.sample_still_id)} alt={`${l.name} sample`} className="h-full w-full object-cover" loading="lazy" /> : <span className="text-sm text-muted">No sample yet</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="type-card">{l.name}</h3>
                  {inUse && <Badge tone="accent">In use</Badge>}
                  {!l.on && <Badge>Off</Badge>}
                </div>
                <p className="text-sm text-muted">{l.blurb}</p>
                {!l.on && owner && <p className="text-sm text-warning">Off for editors: only you can use it.</p>}
                {!inUse && (
                  <Button variant="secondary" disabled={closed} reason={closed ? "Not switched on yet" : null} busy={busy === l.id} onClick={() => onPick(l)}>
                    Use this look
                  </Button>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/** "Look: House ▾" for a script or a video: opens the picker, saves at once (free) with Undo. Read only once published. Hidden until the server offers looks. */
export function LookSetting({ value, scriptId, queryKey, readOnly }: { value: string | null | undefined; scriptId: number; queryKey: unknown[]; readOnly?: boolean }) {
  const looks = useLooks();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const save = useMutation({
    mutationFn: (look: string) => must(api.PATCH("/scripts/{script_id}", { params: { path: { script_id: scriptId } }, body: { look } })),
    onSuccess: async (_r, look) => {
      await queryClient.invalidateQueries({ queryKey });
      return look;
    },
  });
  if (looks.isPending) return <Skeleton className="h-control w-32" />;
  if (!looks.data) return null; // the server doesn't offer looks yet
  const id = value ?? looks.data[0]?.id ?? "house";
  const name = looks.data.find((l) => l.id === id)?.name ?? "House";
  if (readOnly) return <Badge icon={Palette}>Look: {name}</Badge>;
  const pick = (l: Look) => {
    const was = id;
    save.mutate(l.id, {
      onSuccess: () => {
        setOpen(false);
        toast(`The look is ${l.name}.`, () => save.mutate(was));
      },
    });
  };
  return (
    <>
      <Button variant="ghost" dense icon={Palette} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        Look: {name}
      </Button>
      {save.isError && !open && <p role="alert" className={errorClass}>{save.error.message}</p>}
      {open && <LookPicker current={id} looks={looks.data} busy={save.isPending ? (save.variables ?? null) : null} error={save.isError ? save.error.message : null} onPick={pick} onClose={() => setOpen(false)} />}
    </>
  );
}
