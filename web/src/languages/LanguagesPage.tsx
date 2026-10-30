import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Select, Skeleton } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { useLanguages } from "./useLanguages";
import { errorText as errorClass } from "../ui";

type Language = components["schemas"]["LanguageOut"];

/** The Languages page (owner, flows VS1): every language, its sample test, and the switch that lets editors write in it. */
export function LanguagesPage() {
  const owner = useMe().data?.role === "owner";
  const list = useLanguages();
  // With no brand at all the shell shows "No brands yet" instead of this page, so there's always one to test with.
  const brands = useBrands().data ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  const brandId = picked ?? brands[0]?.id ?? null;
  if (!owner) return <p className="p-6">Only the owner manages languages.</p>;
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="type-page">Languages</h1>
        <p className="text-sm text-muted">What scripts can be written in. A language is on for editors once you've read and approved its test script.</p>
      </div>
      {brands.length > 1 && (
        <div className="max-w-xs">
          <Select label="Test with" hint="The test script is written for this brand." value={brandId ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </Select>
        </div>
      )}
      {list.isPending && <Skeleton className="h-40" />}
      {list.isError && <Banner title="Couldn't load the languages." action={<Button variant="secondary" onClick={() => void list.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {(list.data ?? []).map((l) => (
          <li key={l.id} aria-label={l.name}>
            <LanguageCard language={l} brandId={brandId} />
          </li>
        ))}
      </ul>
    </main>
  );
}

function LanguageCard({ language: l, brandId }: { language: Language; brandId: number | null }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const english = l.id === "en";
  const path = { params: { path: { language: l.id } } };
  const sample = useQuery({
    enabled: !english,
    queryKey: ["language-sample", l.id],
    queryFn: async () => (await must(api.GET("/languages/{language}/sample", path))).data!,
    refetchInterval: (q) => (q.state.data?.status === "making" ? 3000 : false),
    retry: false, // a failed load says why at once, with Try again
  });
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["languages"] }), queryClient.invalidateQueries({ queryKey: ["language-sample", l.id] })]);
  const fail = (e: Error) => toast(e.message, undefined, "error");
  const test = useMutation({
    mutationFn: () => must(api.POST("/languages/{language}/sample", { ...path, body: { brand_id: brandId! } })),
    onSuccess: refresh,
  });
  const setOn = (on: boolean) => must(api.PATCH("/languages/{language}", { ...path, body: { on } }));
  const turn = useMutation({
    mutationFn: setOn,
    onSuccess: async (_r, on) => {
      await refresh();
      // Switching off has Undo; scripts already in the language keep it.
      toast(on ? `${l.name} is on for editors.` : `${l.name} is off for editors. Scripts in it keep it; new scripts start in English.`, () => void setOn(!on).then(refresh, fail));
    },
  });
  const setRejected = (rejected: boolean) => must(api.PATCH("/languages/{language}/sample", { ...path, body: { rejected } }));
  const reject = useMutation({
    mutationFn: () => setRejected(true),
    onSuccess: async () => {
      await refresh();
      toast(`Rejected: ${l.name} stays off.`, () => void setRejected(false).then(refresh, fail));
    },
  });
  const s = sample.data;
  const refused = [test, turn, reject].find((m) => m.isError)?.error?.message;
  const testButton = (label: string) => (
    <Button variant={s?.status === "ready" ? "ghost" : "primary"} charge="estimate" price={s?.credits} busy={test.isPending} disabled={brandId === null} onClick={() => test.mutate()}>
      {label}
    </Button>
  );
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="type-card">{l.name}</h2>
        {l.on ? <Badge tone="success">On · editors can pick it</Badge> : <Badge>Off for editors</Badge>}
      </div>
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {english ? (
        <p className="text-sm text-muted">English is always on.</p>
      ) : !s ? (
        sample.isError ? (
          <div className="space-y-2">
            <p role="alert" className={errorClass}>{sample.error.message}</p>
            <Button variant="secondary" onClick={() => void sample.refetch()}>Try again</Button>
          </div>
        ) : (
          <Skeleton className="h-control w-48" />
        )
      ) : s.status === "making" ? (
        <p role="status" className="text-sm text-muted">Writing a short {l.name} script…</p>
      ) : (
        <div className="space-y-2">
          {s.text && (
            <pre className={`whitespace-pre-wrap rounded-md bg-surface-2 p-3 font-sans text-sm ${s.status === "rejected" ? "text-muted line-through" : ""}`} aria-label={`${l.name} test script`}>
              {s.text}
            </pre>
          )}
          {s.status === "failed" && <p role="alert" className={errorClass}>{s.reason || "The test didn't finish. Nothing was charged for it."}</p>}
          {s.status === "rejected" && <p className="text-sm text-muted">Rejected: {l.name} stays off.</p>}
          {s.test_site && !l.on && <p className="text-sm text-muted">{s.test_site}</p>}
          <div className="flex flex-wrap gap-2">
            {l.on ? (
              <Button variant="secondary" busy={turn.isPending} onClick={() => turn.mutate(false)}>Switch off</Button>
            ) : s.status === "ready" ? (
              <>
                <Button busy={turn.isPending} onClick={() => turn.mutate(true)}>Switch on for editors</Button>
                <Button variant="secondary" busy={reject.isPending} onClick={() => reject.mutate()}>Reject</Button>
                {testButton("Test again")}
              </>
            ) : (
              testButton(s.status === "failed" ? "Try again" : s.status === "rejected" ? "Test again" : `Test ${l.name}`)
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
