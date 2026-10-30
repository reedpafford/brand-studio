import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Panel, Select, Skeleton } from "../components";
import { useLooks, type Look } from "../scripts/Looks";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** The Looks page (owner, flows ST3): every look, its sample, and the switch that lets editors pick it. */
export function LooksPage() {
  const owner = useMe().data?.role === "owner";
  const looks = useLooks();
  // With no brand at all the shell shows "No brands yet" instead of this page, so there's always one to sample with.
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
  const [viewing, setViewing] = useState(false);
  const s = sample.data;
  const still = s?.still_id ?? l.sample_still_id;
  const clip = s?.clip_id ?? l.sample_clip_id;
  const clipComing = s?.status === "making" && !!s.still_id; // the still is in, the 5 s clip is still being made
  const refused = [make, turn].find((m) => m.isError)?.error?.message;
  const actions = (
    <>
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {house ? (
        <p className="text-sm text-muted">The house look is always on.</p>
      ) : l.on ? (
        <Button variant="secondary" busy={turn.isPending} onClick={() => turn.mutate(false)}>Switch off</Button>
      ) : brandId === null ? null : !s ? (
        sample.isError ? <p className="text-sm text-muted">{sample.error.message}</p> : <Skeleton className="h-control w-48" />
      ) : s.status === "making" ? (
        <p role="status" className="text-sm text-muted">{clipComing ? "The still is in. Clip coming…" : "Making the sample: one still, then a 5 s clip…"}</p>
      ) : s.status === "ready" ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button busy={turn.isPending} onClick={() => turn.mutate(true)}>Switch on for editors</Button>
            <Button variant="ghost" busy={make.isPending} charge="estimate" price={s.credits} onClick={() => make.mutate(s.hero ? s.hero.id : who === "sample" ? null : who)}>Make another sample</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {s.status === "failed" && <p role="alert" className={errorClass}>{s.reason || "The sample didn't finish. Nothing was charged."}</p>}
          {s.hero ? (
            <p className="text-sm text-muted">One still and one 5 s clip of {s.hero.name}, the brand's hero.</p>
          ) : s.look.own_sample ? (
            <p className="text-sm text-muted">One still and one 5 s clip of the look's own sample character.</p>
          ) : (
            <Select label="Who's in the sample?" value={who} onChange={(e) => setWho(e.target.value === "sample" ? "sample" : Number(e.target.value))}>
              <option value="sample">A sample character (from the look)</option>
              {s.characters.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          )}
          {s.test_site && <p className="text-sm text-muted">{s.test_site}</p>}
          <Button charge="estimate" price={s.credits} busy={make.isPending} onClick={() => make.mutate(s.hero ? s.hero.id : who === "sample" ? null : who)}>
            {s.status === "failed" ? "Try again" : "Make a sample"}
          </Button>
        </div>
      )}
    </>
  );
  return (
    <Card className="space-y-3">
      {/* The sample is portrait (9:16): shown whole, never cropped. Tapping it opens the full still and the clip. */}
      {still ? (
        <button type="button" onClick={() => setViewing(true)} aria-label={`Open the ${l.name} sample`} className="relative block h-64 w-full overflow-hidden rounded-md bg-surface-2">
          <img src={fileUrl(still)} alt={`${l.name} sample`} className="absolute inset-0 h-full w-full object-contain" />
          {(clip || clipComing) && <span className="absolute bottom-2 left-2"><Badge>{clip ? "▶ 5 s clip" : "Clip coming…"}</Badge></span>}
        </button>
      ) : (
        <div className="grid h-64 place-items-center rounded-md bg-surface-2">
          <span className="text-sm text-muted">No sample yet</span>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="type-card">{l.name}</h2>
        {l.on ? <Badge tone="success">On · editors can pick it</Badge> : <Badge>Off for editors</Badge>}
      </div>
      <p className="text-sm text-muted">{l.blurb}</p>
      {actions}
      {viewing && still && (
        <Panel title={`${l.name} sample`} onClose={() => setViewing(false)}>
          <div className="space-y-3">
            <img src={fileUrl(still)} alt={`${l.name} sample, full size`} className="mx-auto max-h-[70dvh] w-auto max-w-full rounded-md object-contain" />
            {clip ? (
              <video controls autoPlay muted loop playsInline src={fileUrl(clip)} className="mx-auto max-h-[70dvh] w-auto max-w-full rounded-md" aria-label={`${l.name} sample clip`} />
            ) : clipComing ? (
              <p role="status" className="text-sm text-muted">Clip coming… It shows here when it's ready.</p>
            ) : null}
            {actions}
          </div>
        </Panel>
      )}
    </Card>
  );
}
