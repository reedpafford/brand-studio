import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Button } from "../components";
import { useLooks } from "../scripts/Looks";
import { useToast } from "../toast";
import { card, errorText as errorClass } from "../ui";
import { orCall } from "../projects/orCall";

/** One approved sheet of a character or place (OR3, Builder-Server-8's #957), newest first. */
type SheetVersion = { file_id: number; look_id: string; made_at: string | null; preferred: boolean };

/** OR3 Preferred look: the approved sheets of a Cast & places item, each in its look, and which one videos use. The owner
 *  picks another (free, Undo); stills and takes made from the one before read Out of date with their usual redo (N6).
 *  Hidden with only one sheet, or on a server without the route. */
export function SheetVersions({ item, kind }: { item: { id: number; name: string }; kind: "character" | "place" }) {
  const owner = useMe().data?.role === "owner";
  const looks = useLooks().data ?? [];
  const queryClient = useQueryClient();
  const toast = useToast();
  const base = `/library/${kind}/${item.id}/sheet`;
  const versions = useQuery({ queryKey: ["sheet-versions", kind, item.id], queryFn: () => orCall<SheetVersion[]>("GET", `${base}/versions`) });
  const refresh = () => Promise.all([["sheet-versions", kind, item.id], ["library", kind], ["assets"]].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  const prefer = (v: { file_id: number; look_id: string }) => orCall<{ was_file_id: number | null }>("POST", `${base}/preferred`, v);
  const pick = useMutation({
    mutationFn: prefer,
    onSuccess: async (r, v) => {
      await refresh();
      const was = r?.was_file_id;
      toast(`${item.name} uses this sheet now. Stills and takes from the other show Out of date.`, was ? () => void prefer({ file_id: was, look_id: v.look_id }).then(refresh, (e: Error) => toast(e.message, undefined, "error")) : undefined);
    },
  });
  const list = versions.data ?? [];
  if (list.length < 2) return null;
  const lookName = (id: string) => looks.find((l) => l.id === id)?.name ?? (id === "house" ? "House" : id);
  return (
    <section aria-label="Sheets" className={`${card} space-y-3`}>
      <div>
        <h2 className="font-medium">Sheets</h2>
        <p className="text-sm text-muted">{owner ? "Videos use the sheet marked In use for its look. Pick another any time, free." : "Videos use the sheet marked In use. Only the owner picks another."}</p>
      </div>
      {pick.isError && <p role="alert" className={errorClass}>{pick.error.message}</p>}
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {list.map((v) => (
          <li key={v.file_id} aria-label={`Sheet ${v.file_id}`} className="space-y-2 text-sm">
            <div className="grid aspect-[9/16] place-items-center overflow-hidden rounded-md bg-surface-2">
              <img src={fileUrl(v.file_id)} alt={`${item.name}, ${lookName(v.look_id)} sheet`} className="h-full w-full object-cover" loading="lazy" />
            </div>
            <p className="flex flex-wrap items-center gap-2">
              <Badge>{lookName(v.look_id)}</Badge>
              {v.preferred && <Badge tone="success">In use</Badge>}
            </p>
            {owner && !v.preferred && (
              <Button variant="secondary" dense busy={pick.isPending && pick.variables?.file_id === v.file_id} onClick={() => pick.mutate({ file_id: v.file_id, look_id: v.look_id })}>
                Use this one
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
