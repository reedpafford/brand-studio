import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Ellipsis, Undo2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Dialog, Field, Menu, MenuItem, Select, Skeleton, useToast, wholeCredits } from "../components";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { Money } from "./parts";
import { useCharges } from "./useUsage";
import { serverTime } from "../time";

const when = (iso: string) => serverTime(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const STATUS: Record<string, string> = { succeeded: "Done", failed: "Didn't finish", running: "Making", queued: "Waiting" };

type Charge = NonNullable<ReturnType<typeof useCharges>["data"]>["pages"][number]["items"][number];
const credits = (n: number) => (n === 1 ? "1 credit" : `${n} credits`);

/** Reed's "Give credits back" on one charge: a reason is required, and it can be done once. */
function GiveBack({ charge }: { charge: Charge }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const give = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/usage/charges/{charge_id}/refund", { params: { path: { charge_id: charge.id } }, body: { reason: reason.trim() } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (d) => {
      setAsking(false);
      toast(`${credits(wholeCredits(d.credits))} given back.`);
      await queryClient.invalidateQueries({ queryKey: ["usage"] });
    },
  });
  const shown = wholeCredits(charge.credits);
  return (
    <>
      <Menu title="Charge actions" align="right" trigger={(t) => <Button variant="ghost" dense icon={Ellipsis} aria-label={`Actions for ${charge.what}`} {...t} />}>
        {(close) => (
          <MenuItem onClick={() => { close(); setReason(""); give.reset(); setAsking(true); }}>
            <Undo2 size={20} strokeWidth={1.75} aria-hidden />
            Give credits back
          </MenuItem>
        )}
      </Menu>
      {asking && (
        <Dialog title={`Give back ${credits(shown)}?`} cancelLabel="Keep the charge" actionLabel="Give credits back" busy={give.isPending} holdReason={reason.trim() ? null : "Say why"} onCancel={() => setAsking(false)} onConfirm={() => give.mutate()}>
          <div className="space-y-3">
            <p>
              For "{charge.what}". The credits go back to {charge.person?.name ? `${charge.person.name}'s week` : "the week"} or the video's budget. The <Money value={charge.cost_usd} estimated={charge.estimated} /> stays on the bill: the service was still paid. This can't be undone, and it can only be done once.
            </p>
            <Field label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} placeholder="Wrong cast in the shot" error={give.isError ? give.error.message : null} />
          </div>
        </Dialog>
      )}
    </>
  );
}

/** The credits cell: the number, or the original number struck through once given back, with its badge (the reason is its tooltip). `words` adds "credits" before the badge on a phone line. */
function CreditsCell({ charge, words }: { charge: Charge; words?: boolean }) {
  const back = charge.refunded;
  if (!back) return <>{words ? credits(charge.credits) : charge.credits}</>;
  return (
    <span className="inline-flex flex-wrap items-center justify-end gap-x-2">
      <del className="text-muted">{wholeCredits(back.credits)}</del>
      <span>{words ? "0 credits" : "0"}</span>
      <span title={back.reason}>
        <Badge>Credits given back</Badge>
      </span>
    </span>
  );
}

/** The plain list of charges, for checking one. Closed until opened. */
export function Charges() {
  const rail = useRail();
  const [open, setOpen] = useState(false);
  const [brand, setBrand] = useState<number | null>(null);
  const brands = useBrands();
  const charges = useCharges(open, brand);
  const items = charges.data?.pages.flatMap((p) => p.items) ?? [];
  const owner = useMe().data?.role === "owner";
  const giveBack = (c: Charge) => (owner && !c.refunded && c.credits > 0 ? <GiveBack charge={c} /> : null);
  return (
    <details className="group border-t border-border pt-3" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="flex min-h-control cursor-pointer list-none items-center gap-2 font-medium [&::-webkit-details-marker]:hidden">
        <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="transition-transform group-open:rotate-90 motion-reduce:transition-none" />
        Every charge
      </summary>
      <div className="mt-3 space-y-3">
        <div className="max-w-60">
          <Select label="Brand" value={brand ?? ""} onChange={(e) => setBrand(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Any</option>
            {brands.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        </div>
        {charges.isError && <Banner title="Couldn't load the charges." action={<Button variant="secondary" onClick={() => void charges.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {charges.isPending && open && <Skeleton className="h-24" />}
        {charges.data && items.length === 0 && <p className="text-muted">No charges yet.</p>}
        {items.length > 0 &&
          (rail ? (
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 pr-3 font-medium">When</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Who</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Brand</th>
                  <th scope="col" className="py-2 pr-3 font-medium">What</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Credits</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">$</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Status</th>
                  <th scope="col" className="py-2"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((c, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3">{when(c.at)}</td>
                    <td className="py-2 pr-3">{c.person?.name ?? "—"}</td>
                    <td className="py-2 pr-3">{c.brand?.name ?? "—"}</td>
                    <td className="py-2 pr-3">{c.what}</td>
                    <td className="py-2 pr-3 text-right"><CreditsCell charge={c} /></td>
                    <td className="py-2 pr-3 text-right"><Money value={c.cost_usd} estimated={c.estimated} /></td>
                    <td className="py-2 pr-3">{STATUS[c.status] ?? c.status}</td>
                    <td className="py-2 text-right">{giveBack(c)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((c, i) => (
                <li key={i} className="flex items-start gap-2 py-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <p>{c.what}</p>
                    <p className="text-sm text-muted">
                      {[c.person?.name, when(c.at)].filter(Boolean).join(" · ")} · <CreditsCell charge={c} words /> · <Money value={c.cost_usd} estimated={c.estimated} />
                    </p>
                  </div>
                  {giveBack(c)}
                </li>
              ))}
            </ul>
          ))}
        {charges.hasNextPage && (
          <Button variant="secondary" busy={charges.isFetchingNextPage} onClick={() => void charges.fetchNextPage()} className="w-full lg:w-auto">
            Show more
          </Button>
        )}
      </div>
    </details>
  );
}
