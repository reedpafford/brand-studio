import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { Badge, Banner, Button, Card, Skeleton } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { useRail } from "../useMedia";
import { useScript } from "./useScript";

type Shot = components["schemas"]["ShotRow"];
type Show = "all" | "lines" | "dropped";

/** 0.4 → "0:00.4", 45 → "0:45". */
const clock = (s: number) => {
  const m = Math.floor(s / 60);
  const [whole, tenth] = (s - m * 60).toFixed(1).split(".");
  return `${m}:${whole.padStart(2, "0")}${tenth === "0" ? "" : `.${tenth}`}`;
};

function ShotRowView({ shot, onSeek }: { shot: Shot; onSeek: (s: number) => void }) {
  return (
    <li className={shot.dropped ? "text-faint" : ""}>
      <button type="button" onClick={() => onSeek(shot.start)} className="flex w-full gap-3 px-4 py-3 text-left hover:bg-surface-2" aria-label={`Shot ${shot.n}, ${clock(shot.start)} to ${clock(shot.end)}`}>
        <span className="w-7 shrink-0 text-sm tabular-nums text-muted">{shot.n}</span>
        <span className="min-w-0 flex-1 space-y-1">
          <span className="block text-sm text-muted">
            <span className="tabular-nums">
              {clock(shot.start)}–{clock(shot.end)}
            </span>
            {" · "}
            {[shot.framing, shot.camera].filter(Boolean).join(" · ")}
          </span>
          <span className="line-clamp-2 block">{shot.action}</span>
          {shot.line && (
            <span className="block font-script">
              {shot.speaker ? `${shot.speaker.toUpperCase()}: ` : ""}
              {shot.line}
            </span>
          )}
        </span>
        {shot.dropped && (
          <span className="shrink-0">
            <Badge>Dropped · live action</Badge>
          </span>
        )}
      </button>
    </li>
  );
}

/** Review the breakdown of an imported reel, read only: the player on one side, every shot on the other. Fixes go through Read it again. */
export function ReelReviewPage() {
  const brandId = Number(useParams().brandId);
  const id = Number(useParams().scriptId);
  const rail = useRail();
  const navigate = useNavigate();
  const toast = useToast();
  const brandName = useBrands().data?.find((b) => b.id === brandId)?.name;
  const script = useScript(id);
  const player = useRef<HTMLVideoElement>(null);
  const [show, setShow] = useState<Show>("all");
  const [hookOpen, setHookOpen] = useState(false);
  const [hookCut, setHookCut] = useState(false);
  const hookText = useRef<HTMLParagraphElement>(null);
  const review = useQuery({
    queryKey: ["reel-breakdown", id],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/scripts/{script_id}/import/breakdown", { params: { path: { script_id: id } } });
      if (!data) throw new Error(response.status === 409 ? errorText(error) : "We couldn't load the breakdown.");
      return data;
    },
  });
  const back = `/b/${brandId}/scripts/${id}`;
  const seek = (s: number) => {
    if (player.current) player.current.currentTime = s;
  };
  const use = () => {
    toast(`Script filled from the reel. Adapt it${brandName ? ` for ${brandName}` : ""}.`);
    navigate(`${back}?step=script`);
  };

  const r = review.data;
  // "Show more" only when the hook is cut off.
  useLayoutEffect(() => {
    const el = hookText.current;
    if (el && !hookOpen) setHookCut(el.scrollHeight > el.clientHeight + 1);
  }, [r?.hook, hookOpen]);
  const shots = r?.shots ?? [];
  const shown = show === "all" ? shots : show === "lines" ? shots.filter((s) => s.line) : shots.filter((s) => s.dropped);
  const inMontage = (n: number) => (show === "all" ? r?.montages.find((m) => n >= m.first && n <= m.last) : undefined);
  const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const counts = r ? `${plural(r.shots.length, "shot")}${r.dropped > 0 ? ` · ${r.dropped} dropped (live action)` : ""} · ${plural(r.lines, "line")}` : "";

  // Montages are one row that opens; everything else is a row of its own.
  const rows: ReactNode[] = [];
  for (let i = 0; i < shown.length; i++) {
    const s = shown[i];
    const m = inMontage(s.n);
    if (m && s.n === m.first) {
      const inside = shown.filter((x) => x.n >= m.first && x.n <= m.last);
      rows.push(
        <li key={`m${m.first}`}>
          <details className="group">
            <summary className="flex min-h-control cursor-pointer list-none items-center gap-2 px-4 py-3 text-muted [&::-webkit-details-marker]:hidden">
              <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 transition-transform group-open:rotate-90 motion-reduce:transition-none" />
              <span className="tabular-nums">
                Shots {m.first}–{m.last} · montage · {m.seconds.toFixed(1)} s
              </span>
            </summary>
            <ul className="divide-y divide-border border-t border-border">
              {inside.map((x) => (
                <ShotRowView key={x.n} shot={x} onSeek={seek} />
              ))}
            </ul>
          </details>
        </li>,
      );
    } else if (!m) {
      rows.push(<ShotRowView key={s.n} shot={s} onSeek={seek} />);
    }
  }

  const useButton = (
    <Button onClick={use} disabled={!r}>
      Use this reel
    </Button>
  );
  return (
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      <Link to={back} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        {script.data?.title ?? "Back"}
      </Link>
      <h1 className="type-page">Review the breakdown</h1>
      {review.isPending && <Skeleton className="h-64" />}
      {review.isError && <Banner tone="warning" title={review.error.message} />}
      {r && (
        <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
          <div className="space-y-3 lg:sticky lg:top-4 lg:self-start">
            {r.video_file_id != null ? <video ref={player} controls src={fileUrl(r.video_file_id)} aria-label="The reel" className="mx-auto aspect-[9/16] max-h-[360px] w-full rounded-md bg-surface-2 object-contain lg:max-h-none" /> : null}
            <p>{r.logline}</p>
            {r.hook && (
              <div className="space-y-1 text-sm text-muted">
                <p ref={hookText} className={hookOpen ? "" : "line-clamp-3"}>
                  Hook · {clock(0)}–{clock(r.hook_seconds)}: {r.hook}
                </p>
                {(hookCut || hookOpen) && (
                  <Button variant="ghost" dense onClick={() => setHookOpen(!hookOpen)} aria-expanded={hookOpen}>
                    {hookOpen ? "Show less" : "Show more"}
                  </Button>
                )}
              </div>
            )}
            <p className="text-sm text-muted">{clock(r.seconds)} long</p>
            {rail && <ActionBar phone={false}>{useButton}</ActionBar>}
          </div>
          <section aria-label="Shots" className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="type-section">Shots</h2>
              <div role="radiogroup" aria-label="Show" className="flex w-full overflow-hidden rounded-md border border-border-strong sm:w-fit">
                {(
                  [
                    ["all", "All"],
                    ["lines", "Lines only"],
                    ["dropped", "Dropped"],
                  ] as const
                ).map(([k, label]) => (
                  <button key={k} type="button" role="radio" aria-checked={show === k} onClick={() => setShow(k)} className={`min-h-control flex-1 whitespace-nowrap px-3 font-medium sm:flex-none lg:min-h-control-dense ${show === k ? "bg-accent-soft text-accent-text" : "text-muted hover:bg-surface-2"}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-sm text-muted">{counts}</p>
            <Card className="p-0 sm:p-0">
              {rows.length === 0 ? <p className="p-4 text-muted">{show === "dropped" ? "No shots were dropped." : "No shots to show."}</p> : <ul className="divide-y divide-border">{rows}</ul>}
            </Card>
          </section>
        </div>
      )}
      {!rail && r && <ActionBar phone>{useButton}</ActionBar>}
    </main>
  );
}
