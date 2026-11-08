import { Check, Clock, Film, LoaderCircle, Mic, PenLine } from "lucide-react";
import { Button } from "../components";
import { said, useAskActions, type Ask } from "./AskCard";

const ICON = { change_line: PenLine, softer: Mic, cut_away: Film, pause: Clock } as const; // change_line: the owner's (rule 31, Reed 7 Nov)

/** What the director can change instead of a locked line (S3-14): the script's words are set, so its reply offers each
 *  thing this video can really make instead, priced as its press charges ("up to"; free when it is). A press makes it at
 *  once: the card says what was chosen and, in the server's words, how it's going (made, watched, the cut made again, or
 *  why not). A choice that can't be made now says why and can't be pressed; the other choices stay pressable. */
export function InsteadCard({ ask: a }: { ask: Ask }) {
  const act = useAskActions(a);
  const chosen = a.choices.filter((c) => c.made);
  const press = (key: string) => act.mutate({ body: { how: "instead", choice: key } });
  return (
    <div className="flex flex-col gap-2">
      <p className="leading-[21px]">{a.question}</p>
      {chosen.length > 0 && (
        <p className="flex items-center gap-2 text-[13px] text-muted">
          <Check size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
          {`You chose: ${chosen.map((c) => c.title).join(", ")}`}
        </p>
      )}
      <div className="mt-0.5 flex flex-col gap-2">
        {a.choices.map((c) => {
          const Icon = ICON[c.do as keyof typeof ICON] ?? Clock;
          const busy = act.isPending && act.variables?.body && (act.variables.body as { choice?: string }).choice === c.key;
          const price = c.price ? `up to ${said(c.price)}` : "free";
          return (
            <div key={c.key} className="flex flex-col gap-1.5">
              <button type="button" disabled={!a.can.includes("instead") || !!c.made || !!c.cannot || act.isPending} onClick={() => press(c.key)} className="flex items-start gap-2 rounded-md border border-border-button px-2.5 py-[9px] text-left text-[13px] enabled:hover:bg-surface-2 disabled:cursor-default max-lg:min-h-control">
                {busy ? <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 animate-spin" /> : <Icon size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />}
                <span className="min-w-0">
                  <span className="block font-semibold">{c.title}</span>
                  <span className="block text-xs leading-4 text-muted">{c.made ? c.said : c.cannot || `${c.why} · ${price}`}</span>
                  {!c.made && c.said && <span className="block text-xs leading-4 text-muted">{c.said}</span>}
                </span>
              </button>
              {c.then && a.can.includes("instead") && (
                // Its one-click fix on the card (rule 22): the take wasn't watched, or its watch's remake wasn't made.
                <Button variant="secondary" dense className="self-start" busy={act.isPending} onClick={() => act.mutate({ body: { how: "instead", choice: c.key, option: "use" } })}>
                  {`${c.then} · free`}
                </Button>
              )}
            </div>
          );
        })}
      </div>
      {act.isError && <p role="alert" className="text-sm text-danger">{act.error?.message}</p>}
    </div>
  );
}
