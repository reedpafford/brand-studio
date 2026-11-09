import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, FileText, Search } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Button, Skeleton } from "../components";
import { finished } from "../freestyle/FromScript";
import { SendError, directed, sentTo } from "../freestyle/useFreestyle";
import { lookName, useLooks } from "../scripts/Looks";
import { letterOf, useDebounced } from "../scripts/status";
import { ActionBar } from "../shell/ActionBar";
import { Press, Under, box, row } from "./NewVideoPage";
import { useEstimate, useSend, usd } from "./useNewVideo";

const PAGE = 50;

/** The brand's scripts that can become a video: an editor sees every published one, with videos or not (S2-05); the
 *  owner's drafts too, once they have words. Pasted sends' scripts are published scripts like any other, so they show.
 *  The server searches (title, description, the script's words) and pages; `more` says the page came back full. */
function useScripts(brandId: number, owner: boolean, q: string, limit: number) {
  return useQuery({
    queryKey: ["scripts", "new-video", brandId, owner, q, limit],
    queryFn: async () => {
      const { data } = await api.GET("/scripts", { params: { query: { brand_id: brandId, ...(q ? { q } : {}), limit } } });
      const all = data ?? [];
      return { more: all.length >= limit, rows: all.filter((s) => directed(s.kind) && (owner ? s.versions.some((v) => v.lines > 0) : s.published && s.versions.some(finished))) };
    },
    placeholderData: (prev) => prev,
  });
}

/** New video › From a saved script (S2-06; S2-05 past the budget): find a script, pick it; its words are set. The
 *  newest finished version is made. An editor's starts at once inside its video's budget, else it goes to the owner. */
export function SavedScripts({ brandId, owner, folder, broll, seg, rail, onScript }: { brandId: number; owner: boolean; folder: number | null; broll: string | null; seg: ReactNode; rail: boolean; onScript: (s: { type: string; look: string } | null) => void }) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const q = useDebounced(text.trim());
  const [limit, setLimit] = useState(PAGE);
  const found = useScripts(brandId, owner, q, limit);
  const rows = { ...found, data: found.data?.rows };
  const looks = useLooks().data;
  const [picked, setPicked] = useState<number | null>(null);
  const script = rows.data?.find((s) => s.id === picked);
  const version = script && (script.versions.filter(finished).at(-1) ?? script.versions.at(-1));
  const send = script && version ? { type: script.format, script_id: script.id, slot: version.slot, shape: "9:16" as const, folder_id: folder, broll_look: broll } : null;
  useEffect(() => onScript(script ? { type: script.format, look: script.look } : null), [script, onScript]);
  const est = useEstimate(send).data;
  const sent = useSend((fs) => navigate(sentTo(fs, owner, brandId)));
  const had = sent.error instanceof SendError ? sent.error.hasVideo : undefined;
  const go = (another = false) => send && !sent.isPending && sent.mutate({ ...send, ...(another ? { make_another: true } : {}) });
  const list = (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      {rows.isPending && <Skeleton className="h-14" />}
      {rows.data?.length === 0 && <p className="px-3 py-3 text-sm text-muted">{q ? "No script matches that." : "No script is ready to make yet."}</p>}
      <ul role="radiogroup" aria-label="Scripts" className="max-h-[340px] overflow-y-auto">
        {rows.data?.map((s) => {
          const on = s.id === picked;
          const ready = s.versions.filter(finished);
          const v = ready.at(-1) ?? s.versions.at(-1)!;
          const made = ready.filter((x) => x.project_id).length;
          const used = !s.published ? "owner only" : made ? `${made} of ${ready.length} videos made` : "none made yet";
          return (
            <li key={s.id} role="radio" aria-checked={on} tabIndex={0} onClick={() => (setPicked(s.id), sent.reset())} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setPicked(s.id), sent.reset())} className={`flex cursor-pointer items-center gap-3 border-t border-border px-3 py-2.5 text-sm first:border-t-0 ${on ? "bg-accent-soft" : "hover:bg-surface-2"}`}>
              <span aria-hidden className={`grid size-4 shrink-0 place-items-center rounded-full border ${on ? "border-accent bg-accent text-on-accent" : "border-border-strong bg-surface"}`}>{on && <Check size={12} />}</span>
              {rail && <FileText size={14} aria-hidden className="shrink-0 text-muted" />}
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-semibold">{s.title}</span>
                <span className="truncate text-xs text-muted">{[s.published ? "Published" : "Draft", `Version ${letterOf(v.slot)}`, s.published && v.lines ? `${v.lines} line${v.lines === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ")}</span>
              </span>
              {rail && <span className="w-[90px] shrink-0 truncate text-muted">{lookName(looks, s.look)}</span>}
              {rail && <span className="w-[130px] shrink-0 text-right text-muted">{used}</span>}
            </li>
          );
        })}
      </ul>
      {found.data?.more && limit < 200 && (
        <div className="border-t border-border px-3 py-2">
          <Button variant="secondary" dense busy={found.isFetching} onClick={() => setLimit(limit + PAGE)}>Show more scripts</Button>
        </div>
      )}
    </div>
  );
  const search = (
    <label className={`flex h-11 lg:h-[30px] items-center gap-2 rounded-md border border-border-strong bg-surface px-2.5 text-sm text-muted focus-within:border-focus ${rail ? "w-[260px]" : "w-full"}`}>
      <Search size={14} aria-hidden />
      <span className="sr-only">Search scripts</span>
      <input type="search" value={text} onChange={(e) => (setText(e.target.value), setLimit(PAGE))} placeholder="Search scripts" className="min-w-0 flex-1 bg-transparent text-text outline-none! placeholder:text-muted" />
    </label>
  );
  const press = <Press owner={owner} est={est} busy={sent.isPending} disabled={!send || !!had} onClick={() => go()} wide={!rail} />;
  const hasVideo = had && (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
      <span className="flex-1">
        This version already has a video ·{" "}
        <Link to={`/b/${brandId}/videos/${had.project_id}`} className="text-accent-text hover:underline">
          Open it
        </Link>
      </span>
      <Button variant="secondary" dense busy={sent.isPending} onClick={() => go(true)}>
        Make another{had.up_to != null && ` · up to ${owner && est?.usd != null ? usd(est.usd) : `${Math.ceil(had.up_to)} credits`}`}
      </Button>
    </div>
  );
  const error = sent.isError && !had && <p role="alert" className="text-sm text-danger">{sent.error.message}</p>;
  if (!rail)
    return (
      <div className="flex flex-col gap-3">
        {search}
        {list}
        {hasVideo}
        {error}
        <ActionBar phone>
          <div className="flex flex-col gap-1">
            {press}
            {send && <Under owner={owner} est={est} phone />}
          </div>
        </ActionBar>
      </div>
    );
  return (
    <>
      <div className={box}>
        <div className="flex items-center gap-3 px-3 pt-2.5">
          {seg}
          {search}
        </div>
        <div className="px-3 pb-2 pt-3">{list}</div>
        {hasVideo && <div className="px-3 pb-2">{hasVideo}</div>}
        <div className={row}>
          <span className="text-sm text-muted">The script’s words are set. The director can still add a note: “end on the capsule”.</span>
          <span className="flex-1" />
          {press}
        </div>
      </div>
      <div className="flex min-h-6 items-center px-1 py-1.5">{send && !owner && <Under owner={owner} est={est} />}</div>
      {error}
    </>
  );
}
