import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Banner, Button, Select, Skeleton } from "../components";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { Money } from "./parts";
import { useCharges } from "./useUsage";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const STATUS: Record<string, string> = { succeeded: "Done", failed: "Didn't finish", running: "Making", queued: "Waiting" };

/** The plain list of charges, for checking one. Closed until opened. */
export function Charges() {
  const rail = useRail();
  const [open, setOpen] = useState(false);
  const [brand, setBrand] = useState<number | null>(null);
  const brands = useBrands();
  const charges = useCharges(open, brand);
  const items = charges.data?.pages.flatMap((p) => p.items) ?? [];
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
                  <th scope="col" className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((c, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3">{when(c.at)}</td>
                    <td className="py-2 pr-3">{c.person?.name ?? "—"}</td>
                    <td className="py-2 pr-3">{c.brand?.name ?? "—"}</td>
                    <td className="py-2 pr-3">{c.what}</td>
                    <td className="py-2 pr-3 text-right">{c.credits}</td>
                    <td className="py-2 pr-3 text-right"><Money value={c.cost_usd} estimated={c.estimated} /></td>
                    <td className="py-2">{STATUS[c.status] ?? c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((c, i) => (
                <li key={i} className="space-y-1 py-3">
                  <p>{c.what}</p>
                  <p className="text-sm text-muted">
                    {[c.person?.name, when(c.at), `${c.credits} credits`].filter(Boolean).join(" · ")} · <Money value={c.cost_usd} estimated={c.estimated} />
                  </p>
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
