import { Fragment, useEffect, type JSX } from "react";
import { Elapsed } from "../clip/History";
import { Button } from "../components";
import type { components } from "../api/schema";
import { errorText as errorClass } from "../ui";
import { useDirections } from "./useDirections";
import type { Script } from "./useScript";

type Mark = components["schemas"]["SuggestionOut"];
const KIND: Record<string, string> = { camera: "Camera", action: "Movement", reaction: "Reaction", brand_screen: "Brand screen", scene_break: "Scene break", cut: "Cut" };
const kindName = (k: string) => KIND[k] ?? k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " ");

/** The script in one short block with the suggested quotes marked (C_Directions' excerpt). */
function Excerpt({ text, marks }: { text: string; marks: Mark[] }) {
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <p className="rounded-lg border border-border bg-surface px-3.5 py-3 type-script text-text">
      {lines.map((line, i) => {
        const quotes = marks.filter((m) => m.line === i + 1 && m.quote && line.includes(m.quote));
        let rest: (string | JSX.Element)[] = [line];
        for (const m of quotes)
          rest = rest.flatMap((part): (string | JSX.Element)[] => {
            if (typeof part !== "string" || !part.includes(m.quote)) return [part];
            const [before, ...after] = part.split(m.quote);
            return [before, <mark key={m.id} className="bg-mark text-text shadow-[inset_0_-2px_0_var(--color-mark-line)]">{m.quote}</mark>, after.join(m.quote)];
          });
        return (
          <Fragment key={i}>
            {i > 0 && " "}
            {rest}
          </Fragment>
        );
      })}
    </p>
  );
}

/** Step 2 (v5 C_Directions): Claude suggests camera, movement, reaction and brand-screen lines for version A. A list on one
 *  grid (the suggestion, its type, Accept and Remove), then "3 of 5 accepted" and Apply; Claude's notes sit beside it. The
 *  words never change; the step is optional. */
export function DirectionsStep({ script: s, onAccepted }: { script: Script; onAccepted: (n: number) => void }) {
  const text = s.versions.find((v) => v.slot === 0)?.text ?? "";
  const e = useDirections(s.id, text);
  const live = e.marks.filter((m) => m.status !== "rejected");
  const accepted = live.filter((m) => m.status === "accepted").length;
  const pending = live.length - accepted;
  // Accepted but not added: Next still goes on, but asks once before dropping them.
  useEffect(() => onAccepted(accepted), [accepted]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onAccepted(0), []); // eslint-disable-line react-hooks/exhaustive-deps
  const failed = e.last?.status === "failed" && e.marks.length === 0;
  const problem = e.start.error ?? e.decide.error ?? e.apply.error;
  return (
    <div className="mx-auto grid max-w-[1024px] gap-6 lg:grid-cols-[minmax(0,680px)_320px]">
      <section aria-label="Suggested directions" className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3 sm:flex-nowrap">
          <div className="min-w-0 basis-full sm:basis-auto sm:flex-1">
            <h2 className="type-card">Suggested directions</h2>
            <p className="text-sm text-muted">Accept the ones you want, then apply them. Only accepted ones are added.</p>
          </div>
          {!s.published && (
            <Button
              className="shrink-0"
              variant="secondary"
              dense
              charge="estimate"
              price={e.cost}
              disabled={e.running || e.start.isPending}
              busy={e.start.isPending}
              onClick={() => (pending === 0 || window.confirm(`Replace the ${pending} waiting suggestions?`)) && e.start.mutate()}
            >
              {e.marks.length > 0 || e.last ? "Suggest again" : "Suggest directions"}
            </Button>
          )}
        </div>
        {e.running && (
          <p role="status" className="text-sm text-muted">
            {e.last?.status === "needs_owner_approval" ? "Waiting for the owner's OK" : <>Reading your script… <Elapsed since={e.last?.created_at ?? new Date().toISOString()} /></>}
          </p>
        )}
        {failed && <p role="alert" className={errorClass}>Suggestions didn't finish. Your script is unchanged. Press Suggest again to try again.</p>}
        {!e.running && !e.last && live.length === 0 && <p className="text-sm text-muted">This step is optional. Ask Claude for suggestions, or press Next to skip it.</p>}
        {!e.running && e.last?.status === "succeeded" && live.length === 0 && <p className="text-sm text-muted">This script already reads well. Nothing to suggest.</p>}
        {live.length > 0 && (
          <>
            <Excerpt text={text} marks={live} />
            <ul aria-label="Suggestions">
              {live.map((m) => {
                const on = m.status === "accepted";
                return (
                  <li key={m.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 border-b border-border py-2 sm:min-h-[68px] sm:grid-cols-[minmax(0,1fr)_112px_196px]">
                    <span className="col-span-2 min-w-0 sm:col-span-1">
                      {m.text}
                      {m.reason && <span className="block text-xs text-muted">Why: {m.reason}</span>}
                    </span>
                    <span className="justify-self-start rounded-sm border border-border px-1.5 text-xs leading-5 text-muted">{kindName(m.kind)}</span>
                    <span className="grid grid-cols-[96px_88px] gap-2">
                      <Button
                        variant="secondary"
                        dense
                        aria-pressed={on}
                        aria-label={`${on ? "Accepted" : "Accept"}: ${m.text}`}
                        className={on ? "!border-accent-soft !bg-accent-soft !text-accent-text" : ""}
                        onClick={() => !on && e.decide.mutate({ id: m.id, verb: "accept" })}
                      >
                        {on ? "Accepted" : "Accept"}
                      </Button>
                      <Button variant="ghost" dense className="text-muted" aria-label={`Remove: ${m.text}`} onClick={() => e.decide.mutate({ id: m.id, verb: "reject" })}>
                        Remove
                      </Button>
                    </span>
                  </li>
                );
              })}
            </ul>
            <div className="flex flex-wrap items-center justify-end gap-3">
              <span className="text-xs tabular-nums text-muted">
                {accepted} of {live.length} accepted
              </span>
              <Button disabled={accepted === 0 || e.apply.isPending} title={accepted === 0 ? "Accept a suggestion first" : undefined} busy={e.apply.isPending} onClick={() => e.apply.mutate()}>
                Apply {accepted} accepted
              </Button>
            </div>
          </>
        )}
        {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
      </section>
      <aside aria-label="Notes" className="flex flex-col gap-2.5 border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
        <h2 className="type-card">Notes</h2>
        <p className="text-xs text-muted">Claude's notes on the words, for information. Only people change the words.</p>
        {e.notes.length === 0 ? (
          <p className="text-sm text-muted">No notes yet.</p>
        ) : (
          <ul className="flex list-disc flex-col gap-2 pl-[18px] text-sm text-muted">
            {e.notes.map((n) => (
              <li key={`${n.line}:${n.text}`}>{n.text}</li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
