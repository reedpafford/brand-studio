import { ArrowUp, Clock } from "lucide-react";
import { Button, creditsLabel, wholeCredits } from "../components";
import { usd, type Price } from "./useNewVideo";

export const box = "rounded-xl border border-border bg-surface shadow-soft transition-[border-color,box-shadow] duration-(--dur-fast) ease-out hover:border-border-button focus-within:border-accent focus-within:shadow-ring";
export const row = "flex flex-wrap items-center gap-1.5 border-t border-border px-3 py-2.5";

/** The press's label (rules 34, 36): the owner sees the most in dollars, an editor in credits; a held send goes to the owner.
 *  A price on its way says so, and one that failed says it's unavailable: never the last price, kept silently. */
export function pressWords(owner: boolean, { est, stale, failed }: Price, go = "Make it") {
  const held = !owner && !!est?.held;
  // The owner's uncapped test site (Reed, 6 Nov): what it will probably cost, never a most.
  const most = failed ? "price unavailable" : !est ? "" : stale ? "updating the price…" : est.expected && est.usd != null ? `about ${usd(est.usd)}` : owner && est.usd != null ? `up to ${usd(est.usd)}` : `up to ${creditsLabel(est.credits)}`;
  return { label: held ? "Send to the owner" : go, most, held };
}

/** The line under the box: what the price means, or why it waits and that no generation starts until then (S2-02, -04,
 *  -05; Reed, 4 Nov: never "nothing spent" before Make it, as the plan is a small spend). */
export function Under({ owner, est, failed, phone }: { owner: boolean; phone?: boolean } & Price) {
  if (failed) return <span role="alert" className="animate-fade text-xs text-danger">Price unavailable: {failed}</span>;
  if (!est) return null;
  if (!owner && est.held) {
    const past = est.budget != null ? `Up to ${wholeCredits(est.credits)} credits is past this video’s budget of ${wholeCredits(est.budget)}, so it goes to the owner first. No generation starts while it waits.` : "The owner approves before any generation starts. You’ll see it in My requests.";
    return (
      <span className="animate-fade flex items-center gap-1.5 text-xs text-warning">
        <Clock size={12} aria-hidden className="shrink-0" /> {past}
      </span>
    );
  }
  if (est.expected) return <span className="animate-fade text-xs text-muted">An estimate of what it will probably cost. Nothing stops it at a limit here; what it really spends shows on the video.</span>;
  if (phone) return <span className="text-xs text-muted">The most it can charge, redos included</span>;
  return <span className="animate-fade text-xs text-muted">{owner ? "Most it can charge, including redos and the director’s time. Usually less." : "Inside this video’s budget, so it starts straight away."}</span>;
}

/** The main press, with the most it can charge after a dot ("Make it · up to $16.86"). */
export function Press({ owner, price, busy, disabled, onClick, go, wide, shortcut }: { owner: boolean; price: Price; busy: boolean; disabled: boolean; onClick: () => void; go?: string; wide?: boolean; /** ⌘↵ sends from this box (the Paste tab only) */ shortcut?: boolean }) {
  const w = pressWords(owner, price, go);
  return (
    <Button busy={busy} disabled={disabled} icon={w.held ? ArrowUp : undefined} onClick={onClick} kbd={shortcut && !wide && !disabled ? "⌘↵" : undefined} className={`${wide ? "w-full" : "shrink-0 whitespace-nowrap"} lg:min-h-8 lg:px-3`}>
      {w.label}
      {!disabled && w.most && (
        <>
          {" "}
          <span className="font-normal opacity-85">· {w.most}</span>
        </>
      )}
    </Button>
  );
}
