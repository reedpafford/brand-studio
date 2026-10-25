import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardPaste, Plus, X } from "lucide-react";
import { api, errorText } from "../api/client";
import { useReferences } from "../projects/BriefPickers";
import { Badge, Banner, Button, Field, Panel, Select, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

type Row = { title: string; description: string; reference: string };
const MAX = 20;
const empty = (): Row => ({ title: "", description: "", reference: "" });

/** "Title — what it's for", one per line. An empty title takes the first 6 words of the description. */
export function parseList(text: string): Row[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const [first, ...rest] = line.split(/\s+[—–-]\s+/);
      const description = rest.join(" — ").trim();
      if (!description) return { title: first.split(/\s+/).slice(0, 6).join(" "), description: first, reference: "" };
      return { title: first.trim() || description.split(/\s+/).slice(0, 6).join(" "), description, reference: "" };
    });
}

/** Reed's many-at-once: rows become drafts first (nothing is written), then Write all asks Claude for every script at one price. */
export function BulkCreate({ brandId, onClose }: { brandId: number; onClose: () => void }) {
  const [rows, setRows] = useState<Row[]>([empty(), empty(), empty()]);
  const [pasting, setPasting] = useState<string | null>(null);
  const [made, setMade] = useState<{ id: number; title: string }[] | null>(null);
  const refs = useReferences();
  const toast = useToast();
  const queryClient = useQueryClient();
  const set = (i: number, patch: Partial<Row>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const bad = rows.map((r) => r.title.trim() === "" || r.description.trim() === "");
  const missing = bad.filter(Boolean).length;
  const [tried, setTried] = useState(false);

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/bulk", {
        body: { scripts: rows.map((r) => ({ brand_id: brandId, title: r.title.trim(), description: r.description.trim(), notes: "", reference_replace: "", text: "", ...(r.reference ? { reference_id: r.reference } : {}) })) },
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      setMade(data.map((d) => ({ id: d.id, title: d.title })));
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });

  const ids = made?.map((m) => m.id) ?? [];
  const estimate = useQuery({
    enabled: ids.length > 0,
    queryKey: ["write-estimate", ids],
    queryFn: async () => (await api.POST("/scripts/write/estimate", { body: { script_ids: ids } })).data ?? null,
  });
  const writeAll = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/write", { body: { script_ids: ids } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (jobs) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast(`Writing ${jobs.length} script${jobs.length === 1 ? "" : "s"}. They'll show as drafts when they're ready.`);
      onClose();
    },
  });

  if (made)
    return (
      <Panel title="Drafts made" onClose={onClose}>
        <div className="space-y-4">
          <ul className="space-y-2">
            {made.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <span className="min-w-0 break-words">{m.title}</span>
                <Badge>Writing</Badge>
              </li>
            ))}
          </ul>
          <div className="space-y-1 rounded-lg border border-border bg-surface-2 p-3">
            <p>
              {made.length} draft{made.length === 1 ? "" : "s"}. Claude can write all their scripts now.
            </p>
            {estimate.data && (
              <p className="text-sm text-muted">
                About {Math.round(estimate.data.credits)} credits ({estimate.data.count} script{estimate.data.count === 1 ? "" : "s"} × {Math.round(estimate.data.credits / Math.max(estimate.data.count, 1))})
              </p>
            )}
          </div>
          {writeAll.isError && <Banner title={writeAll.error.message}>Nothing was charged.</Banner>}
          <Button price={estimate.data?.credits} busy={writeAll.isPending} disabled={!estimate.data} onClick={() => writeAll.mutate()} className="w-full">
            Write all scripts
          </Button>
          <Button variant="ghost" onClick={onClose} className="w-full">
            Not now
          </Button>
        </div>
      </Panel>
    );

  return (
    <Panel title="Bulk create" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          setTried(true);
          if (missing === 0) create.mutate();
        }}
      >
        <p className="text-sm text-muted">Nothing is written until you press Write all.</p>
        <ul className="space-y-4">
          {rows.map((r, i) => (
            <li key={i} className={`space-y-2 rounded-lg border p-3 ${tried && bad[i] ? "border-danger" : "border-border"}`}>
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <Field label={`Title ${i + 1}`} value={r.title} maxLength={200} onChange={(e) => set(i, { title: e.target.value })} />
                </div>
                <button type="button" aria-label={`Remove row ${i + 1}`} disabled={rows.length === 1} onClick={() => setRows((x) => x.filter((_, j) => j !== i))} className="mt-6 grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 disabled:opacity-40">
                  <X size={20} strokeWidth={1.75} aria-hidden />
                </button>
              </div>
              <TextArea label={`What it's for ${i + 1}`} rows={2} maxLength={2000} value={r.description} onChange={(e) => set(i, { description: e.target.value })} />
              {(refs.data?.length ?? 0) > 0 && (
                <Select label={`Reference ${i + 1}`} value={r.reference} onChange={(e) => set(i, { reference: e.target.value })}>
                  <option value="">None</option>
                  {refs.data?.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </Select>
              )}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" icon={Plus} disabled={rows.length >= MAX} onClick={() => setRows((r) => [...r, empty()])}>
            Add a row
          </Button>
          <Button type="button" variant="ghost" icon={ClipboardPaste} onClick={() => setPasting("")}>
            Paste a list
          </Button>
        </div>
        {pasting !== null && (
          <div className="space-y-2">
            <TextArea label="One script per line: Title — what it's for" rows={5} value={pasting} onChange={(e) => setPasting(e.target.value)} />
            <div className="flex gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={!pasting.trim()}
                onClick={() => {
                  const added = parseList(pasting).slice(0, MAX);
                  setRows((r) => [...r.filter((x) => x.title.trim() || x.description.trim()), ...added].slice(0, MAX));
                  setPasting(null);
                }}
              >
                Add these rows
              </Button>
              <Button type="button" variant="ghost" onClick={() => setPasting(null)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
        {create.isError && <Banner title="The drafts weren't made. Nothing was charged." action={<Button variant="secondary" onClick={() => create.mutate()}>Try again</Button>}>{create.error.message}</Banner>}
        {tried && missing > 0 && <p role="alert" className={errorClass}>Give every row a title and what it's for ({missing} row{missing === 1 ? "" : "s"} need{missing === 1 ? "s" : ""} it).</p>}
        <Button type="submit" busy={create.isPending} className="w-full">
          Make {rows.length} draft{rows.length === 1 ? "" : "s"}
        </Button>
      </form>
    </Panel>
  );
}
