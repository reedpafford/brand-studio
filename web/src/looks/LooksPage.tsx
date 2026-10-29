import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Select, Skeleton } from "../components";
import { useLooks, type Look } from "../scripts/Looks";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** The Looks page (owner, flows ST3): every look, its sample, and the switch that lets editors pick it. */
export function LooksPage() {
  const owner = useMe().data?.role === "owner";
  const looks = useLooks();
  const brands = useBrands().data ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  const brandId = picked ?? brands[0]?.id ?? null;
  if (!owner) return <p className="p-6">Only the owner manages looks.</p>;
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="type-page">Looks</h1>
        <p className="text-sm text-muted">How the pictures are drawn. A look is on for editors once you've seen its sample.</p>
      </div>
      {brands.length > 1 && (
        <div className="max-w-xs">
          <Select label="Sample with" hint="The sample uses this brand's hero." value={brandId ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </Select>
        </div>
      )}
      {looks.isPending && <Skeleton className="h-40" />}
      {looks.isError && <Banner title="Couldn't load the looks." action={<Button variant="secondary" onClick={() => void looks.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {looks.data === null && <p className="text-sm text-muted">Looks aren't switched on here yet.</p>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {(looks.data ?? []).map((l) => (
          <li key={l.id} aria-label={l.name}>
            <LookCard look={l} brandId={brandId} />
          </li>
        ))}
      </ul>
    </main>
  );
}

function LookCard({ look: l, brandId }: { look: Look; brandId: number | null }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const house = l.id === "house";
  const sample = useQuery({
    enabled: brandId !== null && !house,
    queryKey: ["look-sample", l.id, brandId],
    queryFn: async () => (await must(api.GET("/looks/{look_id}/sample", { params: { path: { look_id: l.id }, query: { brand_id: brandId! } } }))).data!,
    refetchInterval: (q) => (q.state.data?.status === "making" ? 3000 : false),
  });
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["looks"] }), queryClient.invalidateQueries({ queryKey: ["look-sample", l.id] })]);
  const [who, setWho] = useState<number | "sample">("sample");
  const make = useMutation({
    mutationFn: (character_id: number | null) => must(api.POST("/looks/{look_id}/sample", { params: { path: { look_id: l.id } }, body: { brand_id: brandId!, character_id } })),
    onSuccess: refresh,
  });
  const setOn = (on: boolean) => must(api.PATCH("/looks/{look_id}", { params: { path: { look_id: l.id } }, body: { on } }));
  const turn = useMutation({
    mutationFn: setOn,
    onSuccess: async (_r, on) => {
      await refresh();
      // Switching off has Undo; videos already using the look keep it.
      toast(on ? `${l.name} is on for editors.` : `${l.name} is off for editors. Videos using it keep it.`, () => void setOn(!on).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
    },
  });
  const s = sample.data;
  const still = s?.still_id ?? l.sample_still_id;
  const refused = [make, turn].find((m) => m.isError)?.error?.message;
  return (
    <Card className="space-y-3">
      <div className="grid aspect-video place-items-center overflow-hidden rounded-md bg-surface-2">
        {still ? <img src={fileUrl(still)} alt={`${l.name} sample`} className="h-full w-full object-cover" /> : <span className="text-sm text-muted">No sample yet</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="type-card">{l.name}</h2>
        {l.on ? <Badge tone="success">On · editors can pick it</Badge> : <Badge>Off for editors</Badge>}
      </div>
      <p className="text-sm text-muted">{l.blurb}</p>
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {house ? (
        <p className="text-sm text-muted">The house look is always on.</p>
      ) : l.on ? (
        <Button variant="secondary" busy={turn.isPending} onClick={() => turn.mutate(false)}>Switch off</Button>
      ) : !s ? (
        sample.isError ? <p className="text-sm text-muted">{sample.error.message}</p> : <Skeleton className="h-control w-48" />
      ) : s.status === "making" ? (
        <p role="status" className="text-sm text-muted">Making the sample: one still, then a 5 s clip…</p>
      ) : s.status === "ready" ? (
        <div className="space-y-2">
          {s.clip_id && <video controls muted src={fileUrl(s.clip_id)} className="w-full rounded-md" aria-label={`${l.name} sample clip`} />}
          <div className="flex flex-wrap gap-2">
            <Button busy={turn.isPending} onClick={() => turn.mutate(true)}>Switch on for editors</Button>
            <Button variant="ghost" busy={make.isPending} price={s.credits} onClick={() => make.mutate(s.hero?.id ?? null)}>Make another sample</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {s.status === "failed" && <p role="alert" className={errorClass}>{s.reason || "The sample didn't finish. Nothing was charged."}</p>}
          {s.hero ? (
            <p className="text-sm text-muted">One still and one 5 s clip of {s.hero.name}, the brand's hero.</p>
          ) : (
            <Select label="Who's in the sample?" value={who} onChange={(e) => setWho(e.target.value === "sample" ? "sample" : Number(e.target.value))}>
              <option value="sample">A sample character (from the look)</option>
              {s.characters.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          )}
          <Button price={s.credits} busy={make.isPending} onClick={() => make.mutate(s.hero ? s.hero.id : who === "sample" ? null : who)}>
            {s.status === "failed" ? "Try again" : "Make a sample"}
          </Button>
        </div>
      )}
    </Card>
  );
}
