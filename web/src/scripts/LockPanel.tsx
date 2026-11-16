import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, Panel, Skeleton, pressLabel } from "../components";
import { errorText as errorClass } from "../ui";
import { useBrandCharacters, type Slot } from "./useCast";
import { refreshJobs } from "../jobs/refresh";

type Character = NonNullable<ReturnType<typeof useBrandCharacters>["data"]>[number];
const MODEL = "nano-banana-pro";
const RESOLUTION = "2K";

/** Lock a role to one of this brand's characters. A character without an approved sheet gets its sheet made right here. */
export function LockPanel({ slot, brandId, locking, onLock, onClose }: { slot: Slot; brandId: number; locking: boolean; onLock: (itemId: number) => void; onClose: () => void }) {
  const chars = useBrandCharacters(brandId);
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: ["models"], queryFn: async () => (await api.GET("/models")).data ?? [] });
  const price = models.data?.find((m) => m.id === MODEL)?.credits_per_unit?.[RESOLUTION];
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", "character"] });
  const path = (c: Character) => ({ kind: "character" as const, item_id: c.id });
  const make = useMutation({
    mutationFn: async (c: Character) => {
      const { data, error } = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path: path(c) }, body: { model_id: MODEL, change: "" } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all([refresh(), refreshJobs(queryClient)]),
  });
  const approve = useMutation({
    mutationFn: async (c: Character) => {
      await must(api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path: path(c) } }));
      return c;
    },
    onSuccess: async (c) => {
      await refresh();
      onLock(c.id);
    },
  });
  const err = make.error ?? approve.error;

  return (
    <Panel wide title={`Lock ${slot.role} to a look`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-muted">Pick one with an approved sheet, or make its sheet here.</p>
        {chars.isPending && <Skeleton className="h-32" />}
        <ul className="grid grid-cols-3 gap-3">
          {(chars.data ?? []).map((c) => {
            const status = c.sheet_status;
            const picture = c.sheet_file_id ?? c.image_file_ids?.[0]; // the sheet whenever there is one, approved or waiting
            const current = slot.locked && slot.library_item_id === c.id; // the look this role is locked to now
            return (
              <li key={c.id} className="min-w-0 space-y-1.5">
                <button
                  type="button"
                  disabled={status !== "approved" || locking}
                  aria-label={status === "approved" ? `Lock to ${c.name}` : `${c.name} has no approved sheet yet`}
                  aria-current={current || undefined}
                  onClick={() => onLock(c.id)}
                  className={`relative block aspect-[9/16] w-full overflow-hidden rounded-lg border bg-surface-2 disabled:opacity-80 ${current ? "border-accent ring-2 ring-accent" : "border-border"}`}
                >
                  {picture && <img src={fileUrl(picture)} alt="" className="size-full object-cover" />}
                  <span className="absolute inset-x-2 bottom-2 truncate text-left text-sm font-semibold text-on-media drop-shadow">{c.name}</span>
                </button>
                {status === "approved" && <Line dot="bg-success">Sheet approved</Line>}
                {status === "none" && (
                  <>
                    <Line>No sheet yet</Line>
                    <Button variant="secondary" dense className="w-full" aria-label={price === undefined ? "Make sheet" : `Make sheet · ${pressLabel(price, "estimate")}`} busy={make.isPending && make.variables?.id === c.id} disabled={make.isPending || price === undefined} onClick={() => make.mutate(c)}>
                      Make sheet
                    </Button>
                    {price !== undefined && <p className="text-center text-xs text-muted">{pressLabel(price, "estimate")}</p>}
                  </>
                )}
                {status === "drawing" && <Line dot="bg-accent">Drawing the sheet…</Line>}
                {status === "waiting_for_owner" && <Line dot="bg-accent">Waiting for the owner's OK</Line>}
                {status === "needs_approval" && (
                  <>
                    <Line dot="bg-warning">Sheet to check</Line>
                    <Button dense className="w-full" aria-label={`Approve ${c.name}'s sheet`} busy={approve.isPending && approve.variables?.id === c.id} disabled={locking} onClick={() => approve.mutate(c)}>
                      Approve
                    </Button>
                  </>
                )}
              </li>
            );
          })}
        </ul>
        {chars.data?.length === 0 && <p className="text-sm text-muted">This brand has no characters yet. Add them in Cast & places.</p>}
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
      </div>
    </Panel>
  );
}

/** A card's status: a dot and words. */
function Line({ dot, children }: { dot?: string; children: string }) {
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${dot ?? "border border-muted"}`} />
      {children}
    </p>
  );
}
