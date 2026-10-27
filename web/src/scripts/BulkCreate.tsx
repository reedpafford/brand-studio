import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardPaste, Plus, X } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { useReferences } from "../projects/BriefPickers";
import { Badge, Banner, Button, Dialog, Field, Panel, Select, TextArea, wholeCredits } from "../components";
import { useToast } from "../toast";
import { weekStop } from "./useScript";
import { LINK, ReelChip } from "./ReelImport";
import { errorText as errorClass } from "../ui";
import { BulkFiles } from "./BulkFiles";
import { forgetVideo, videoUploader } from "./uploadVideo";
import { MAX_REELS, useFileQueue, type Uploader } from "./videoUploads";

type ReelRow = components["schemas"]["ReelRow"];
type Row = { title: string; description: string; reference: string };
const MAX = MAX_REELS;
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
      if (!description) return { title: first.split(/\s+/).slice(0, 6).join(" "), description: "", reference: "" };
      return { title: first.trim() || description.split(/\s+/).slice(0, 6).join(" "), description, reference: "" };
    });
}

/** What is being read: "7 reels", or "4 reel links and 3 videos" when both kinds are in the queue. */
function reading(kinds: { [key: string]: number }, total: number) {
  const links = kinds.links ?? 0;
  const videos = kinds.videos ?? 0;
  if (links > 0 && videos > 0) return `${links} reel link${links === 1 ? "" : "s"} and ${videos} video${videos === 1 ? "" : "s"}`;
  return `${total} reel${total === 1 ? "" : "s"}`;
}

/** Reed's many-at-once: rows become drafts first (nothing is written), then Write all asks Claude for every script at one price. */
export function BulkCreate({ brandId, onClose, uploader }: { brandId: number; onClose: () => void; uploader?: Uploader }) {
  const [rows, setRows] = useState<Row[]>([empty(), empty(), empty()]);
  const [pasting, setPasting] = useState<string | null>(null);
  const [made, setMade] = useState<{ id: number; title: string; reel?: ReelRow | null }[] | null>(null);
  // Rows, or one Instagram reel link per line (each becomes a draft that adapts its reel).
  const [mode, setMode] = useState<"rows" | "links">("rows");
  const [links, setLinks] = useState("");
  const [newLines, setNewLines] = useState(false);
  const [change, setChange] = useState("");
  const linkList = links.split("\n").map((l) => l.trim()).filter(Boolean);
  const badLinks = linkList.map((l, i) => (LINK.test(l) ? 0 : i + 1)).filter(Boolean);
  const tooMany = linkList.length > MAX;
  const goodLinks = linkList.length - badLinks.length; // the button counts only real reel links
  // Video files go in the same queue as the links: up to MAX reels in all, uploading as soon as they are added.
  const files = useFileQueue(useMemo(() => uploader ?? videoUploader(brandId), [uploader, brandId]), MAX - linkList.length, forgetVideo);
  const [stopping, setStopping] = useState(false);
  const closePanel = () => (files.uploading > 0 ? setStopping(true) : onClose());
  const reelCount = goodLinks + files.ready.length;
  // Reel links: why Make N drafts can't be pressed yet.
  const holdReason =
    mode !== "links" ? null : reelCount === 0 && linkList.length === 0 && files.rows.length === 0 ? "Add a reel link or a video first" : files.uploading > 0 ? `Wait for the uploads to finish (${files.uploading} left)` : badLinks.length > 0 ? "Fix the lines that aren't reel links" : tooMany ? `Up to ${MAX} links` : reelCount === 0 ? "Add a reel link or a video first" : null;
  const refs = useReferences();
  const { data: me } = useMe();
  const editor = me?.role !== undefined && me.role !== "owner";
  const week = useQuery({ enabled: editor, queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  const toast = useToast();
  const queryClient = useQueryClient();
  const set = (i: number, patch: Partial<Row>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const bad = rows.map((r) => r.title.trim() === "" || r.description.trim() === "");
  const missing = bad.filter(Boolean).length;
  const [tried, setTried] = useState(false);

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/bulk", {
        body: mode === "links"
          ? {
              // One ordered list: the links, then the uploaded videos in the order they were added. A refused upload has no id and is never sent.
              scripts: [
                ...linkList.map((url) => ({ brand_id: brandId, reel_url: url })),
                ...files.ready.flatMap((f) => (f.id === null ? [] : [{ brand_id: brandId, upload_id: f.id }])),
              ].map((row) => ({ ...row, description: "", notes: "", reference_replace: change.trim(), new_lines: newLines, text: "" })),
            }
          : { scripts: rows.map((r) => ({ brand_id: brandId, title: r.title.trim(), description: r.description.trim(), notes: "", reference_replace: "", text: "", ...(r.reference ? { reference_id: r.reference } : {}) })) },
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      setMade(data.map((d) => ({ id: d.id, title: d.title, reel: d.reel })));
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });

  const ids = made?.map((m) => m.id) ?? [];
  const reels = mode === "links";
  const estimate = useQuery({
    enabled: ids.length > 0,
    queryKey: ["write-estimate", ids],
    queryFn: async () => (await api.POST("/scripts/write/estimate", { body: { script_ids: ids } })).data ?? null,
  });
  // An editor is billed to their weekly allowance and is declined past it. There is no Ask Reed.
  const stopped = editor && !!estimate.data && estimate.data.credits_left !== null && estimate.data.credits > estimate.data.credits_left;
  const writeAll = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/write", { body: { script_ids: ids } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (jobs) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast(reels ? `Reading ${jobs.length} reel${jobs.length === 1 ? "" : "s"} and writing their scripts. They'll show as drafts when they're ready.` : `Writing ${jobs.length} script${jobs.length === 1 ? "" : "s"}. They'll show as drafts when they're ready.`);
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
                <span className="min-w-0 break-words">
                  {m.title}
                  {m.reel?.file_name && <span className="block text-sm text-muted">{m.reel.file_name}</span>}
                </span>
                {reels ? <ReelChip reel={(estimate.data?.failed ?? []).includes(m.id) ? { source: "link", ...m.reel, status: "failed", seconds: null, fetch_error: m.reel?.fetch_error } : m.reel} /> : <Badge>Writing</Badge>}
              </li>
            ))}
          </ul>
          <div className="space-y-1 rounded-lg border border-border bg-surface-2 p-3">
            <p>
              {made.length} draft{made.length === 1 ? "" : "s"}. Claude can write all their scripts now.
            </p>
            {estimate.data && (
              <p className="text-sm text-muted">
                {reels && estimate.data.reading > 0
                  ? `About ${wholeCredits(estimate.data.credits)} credits: reading ${reading(estimate.data.reels, estimate.data.reading)} (${wholeCredits(estimate.data.read_credits)}) and writing ${estimate.data.writing} script${estimate.data.writing === 1 ? "" : "s"} and cast${estimate.data.writing === 1 ? "" : "s"} (${wholeCredits(estimate.data.write_credits)})`
                  : `About ${wholeCredits(estimate.data.credits)} credits (${estimate.data.count} script${estimate.data.count === 1 ? "" : "s"} × ${wholeCredits(estimate.data.credits / Math.max(estimate.data.count, 1))})`}
              </p>
            )}
          </div>
          {writeAll.isError && <Banner title={writeAll.error.message}>Nothing was charged.</Banner>}
          <Button price={estimate.data?.credits} busy={writeAll.isPending} disabled={!estimate.data || stopped} reason={stopped && week.data && estimate.data ? weekStop(week.data, estimate.data.credits) : stopped ? "That's more than the credits you have left this week. It resets on Monday." : undefined} onClick={() => writeAll.mutate()} className="w-full">
            Write all scripts
          </Button>
          <Button variant="ghost" onClick={onClose} className="w-full">
            Not now
          </Button>
        </div>
      </Panel>
    );

  return (
    <Panel title="Bulk create" onClose={closePanel}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          setTried(true);
          if (mode === "links" ? reelCount > 0 && files.uploading === 0 && badLinks.length === 0 && !tooMany : missing === 0) create.mutate();
        }}
      >
        <div role="radiogroup" aria-label="How to add them" className="flex w-full overflow-hidden rounded-md border border-border-strong sm:w-fit">
          {(
            [
              ["rows", "Rows"],
              ["links", "Reels"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" role="radio" aria-checked={mode === id} onClick={() => setMode(id)} className={`min-h-control flex-1 whitespace-nowrap px-4 font-medium sm:flex-none ${mode === id ? "bg-accent-soft text-accent-text" : "text-muted hover:bg-surface-2"}`}>
              {label}
            </button>
          ))}
        </div>
        <p className="text-sm text-muted">Nothing is written until you press Write all.</p>
        {mode === "links" && (
          <div className="space-y-4">
            <TextArea label="Paste reel links, one per line" rows={6} placeholder="https://www.instagram.com/reel/…" value={links} onChange={(e) => setLinks(e.target.value)} hint={`Up to ${MAX} links.`} />
            {tried && linkList.length === 0 && <p role="alert" className={errorClass}>Paste at least one reel link.</p>}
            {badLinks.length > 0 && (
              <ul role="alert" className={`${errorClass} space-y-0.5`}>
                {badLinks.map((n) => (
                  <li key={n}>Line {n} isn't a reel link</li>
                ))}
              </ul>
            )}
            {tooMany && <p role="alert" className={errorClass}>That's {linkList.length} links. Up to {MAX} at a time.</p>}
            <BulkFiles queue={files} />
            <div className="space-y-1">
              <label className="flex min-h-control items-center gap-3">
                <input type="checkbox" role="switch" className="size-5" checked={newLines} onChange={(e) => setNewLines(e.target.checked)} />
                Write new lines in the same style
              </label>
              <p className="text-sm text-muted">Off: keep the reel's lines and rewrite only what the brand swap needs.</p>
            </div>
            <TextArea label="What to change (optional)" rows={2} maxLength={2000} placeholder="For example: reselling becomes trading." value={change} onChange={(e) => setChange(e.target.value)} />
          </div>
        )}
        {mode === "rows" && <ul className="space-y-4">
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
        </ul>}
        {mode === "rows" && <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" icon={Plus} disabled={rows.length >= MAX} onClick={() => setRows((r) => [...r, empty()])}>
            Add a row
          </Button>
          <Button type="button" variant="ghost" icon={ClipboardPaste} onClick={() => setPasting("")}>
            Paste a list
          </Button>
        </div>}
        {mode === "rows" && pasting !== null && (
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
        {mode === "rows" && tried && missing > 0 && <p role="alert" className={errorClass}>Give every row a title and what it's for ({missing} row{missing === 1 ? "" : "s"} need{missing === 1 ? "s" : ""} it).</p>}
        <Button type="submit" busy={create.isPending} disabled={!!holdReason} reason={holdReason} className="w-full">
          {`Make ${mode === "links" ? reelCount : rows.length} draft${(mode === "links" ? reelCount : rows.length) === 1 ? "" : "s"}`}
        </Button>
        {mode === "links" && files.problems > 0 && <p className="text-sm text-muted">{files.problems} file{files.problems === 1 ? " won't be" : "s won't be"} added.</p>}
        {stopping && (
          <Dialog title="Stop the uploads?" cancelLabel="Keep uploading" actionLabel="Stop and close" danger onCancel={() => setStopping(false)} onConfirm={() => { files.stopAll(); onClose(); }}>
            The files you added won't be kept.
          </Dialog>
        )}
      </form>
    </Panel>
  );
}
