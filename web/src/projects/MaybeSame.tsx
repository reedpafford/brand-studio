import { Users } from "lucide-react";
import { Badge, Button } from "../components";

/** Two roles the server thinks may be one person. `into` is the role to keep; `why` is the server's plain reason. */
export type Pair = { a: number; b: number; into: number; why: string };

/** The note's id, so the badge on a role can scroll to it. */
export const pairId = (p: Pair) => `maybe-same-${p.a}-${p.b}`;

const MAX = 3;

function PairNote({ pair, name, outlined, onMerge, onDismiss }: { pair: Pair; name: (id: number) => string; outlined: boolean; onMerge: (p: Pair) => void; onDismiss: (p: Pair) => void }) {
  return (
    <div id={pairId(pair)} className={`space-y-1 rounded-lg border border-border bg-warning-soft p-3 text-sm ${outlined ? "ring-2 ring-warning" : ""}`}>
      <p className="flex items-start gap-2 font-medium text-text">
        <Users size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
        These may be the same person: {name(pair.a)} and {name(pair.b)}.
      </p>
      <p className="text-xs text-muted">{pair.why}</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" dense aria-label={`Merge ${name(pair.a)} and ${name(pair.b)}`} onClick={() => onMerge(pair)}>
          Merge
        </Button>
        <Button variant="ghost" dense aria-label={`${name(pair.a)} and ${name(pair.b)} are different`} onClick={() => onDismiss(pair)}>
          They're different
        </Button>
      </div>
    </div>
  );
}

/** "These may be the same person": one note per pair, at most three; the rest wait under a closed disclosure. It is advice and never blocks anything. */
export function MaybeSame(props: { pairs: Pair[]; name: (id: number) => string; outlined?: string | null; onMerge: (p: Pair) => void; onDismiss: (p: Pair) => void }) {
  if (props.pairs.length === 0) return null;
  const show = props.pairs.slice(0, MAX);
  const more = props.pairs.slice(MAX);
  const note = (p: Pair) => <PairNote key={pairId(p)} pair={p} name={props.name} outlined={props.outlined === pairId(p)} onMerge={props.onMerge} onDismiss={props.onDismiss} />;
  return (
    <div className="space-y-2" aria-label="Roles that may be the same person">
      {show.map(note)}
      {more.length > 0 && (
        <details>
          <summary className="min-h-11 cursor-pointer text-sm text-muted sm:min-h-0">
            {more.length} more pair{more.length === 1 ? "" : "s"} may be the same person
          </summary>
          <div className="mt-2 space-y-2">{more.map(note)}</div>
        </details>
      )}
    </div>
  );
}

/** "May be the same as Kimchi" on a role's row. Tapping it goes to the note. */
export function MaybeSameBadge({ other, onClick }: { other: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex min-h-11 items-center sm:min-h-0">
      <Badge tone="warning">May be the same as {other}</Badge>
    </button>
  );
}
