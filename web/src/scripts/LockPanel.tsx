import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, Panel, Skeleton, creditsLabel } from "../components";
import { errorText as errorClass } from "../ui";
import { useBrandCharacters, type Slot } from "./useCast";

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
    onSuccess: () => Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ["jobs"] })]),
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
  const cost = price === undefined ? undefined : price;

  return (
    <Panel title={`Lock ${slot.role} to a look`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-muted">Characters from Cast & places. One without an approved sheet can have its sheet made here.</p>
        {chars.isPending && <Skeleton className="h-32" />}
        <ul className="grid grid-cols-2 gap-3">
          {(chars.data ?? []).map((c) => {
            const status = c.sheet_status;
            const picture = status === "needs_approval" && c.sheet_file_id ? c.sheet_file_id : c.image_file_ids?.[0];
            return (
              <li key={c.id} className="space-y-2">
                <button
                  type="button"
                  disabled={status !== "approved" || locking}
                  aria-label={status === "approved" ? `Lock to ${c.name}` : `${c.name} has no approved sheet yet`}
                  onClick={() => onLock(c.id)}
                  className="relative block aspect-[9/16] w-full overflow-hidden rounded-lg border border-border bg-surface-2 disabled:opacity-80"
                >
                  {picture && <img src={fileUrl(picture)} alt="" className="size-full object-cover" />}
                  <span className="absolute inset-x-2 bottom-2 text-left font-display font-bold text-on-media drop-shadow">{c.name}</span>
                </button>
                {status === "none" && (
                  <div className="space-y-1">
                    <p className="text-sm text-muted">No approved sheet yet</p>
                    <Button variant="secondary" dense className="w-full" charge="estimate" price={cost} busy={make.isPending && make.variables?.id === c.id} disabled={make.isPending} onClick={() => make.mutate(c)}>
                      Make sheet
                    </Button>
                  </div>
                )}
                {status === "drawing" && <p className="text-sm text-muted">Drawing the sheet…</p>}
                {status === "waiting_for_owner" && <p className="text-sm text-muted">Not started</p>}
                {status === "needs_approval" && (
                  <div className="space-y-1">
                    <p className="text-sm text-muted">Check the sheet, then approve it to lock {slot.role}.</p>
                    <div className="flex flex-col gap-2">
                      <Button dense className="w-full" aria-label={`Approve ${c.name}'s sheet`} busy={approve.isPending && approve.variables?.id === c.id} disabled={locking} onClick={() => approve.mutate(c)}>
                        Approve
                      </Button>
                      <Button variant="secondary" dense className="w-full" aria-label={`Redo ${c.name}'s sheet`} disabled={make.isPending} onClick={() => make.mutate(c)}>
                        Redo{price !== undefined ? ` · ${creditsLabel(price)}` : ""}
                      </Button>
                    </div>
                  </div>
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
