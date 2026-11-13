import { CircleStop } from "lucide-react";
import { Link } from "react-router-dom";
import { stoppedReply, useTryAgain, type Progress } from "../videos/RunCard";
import { Popover } from "./Popover";
import { PressButton } from "./VideoStart";
import { once, type Press } from "./videoData";

/** Stop, which asks first in a small confirmation under its button; only its own Stop sends anything. */
export function StopButton({ busy, onStop }: { busy: boolean; onStop: () => void }) {
  return (
    <Popover
      label="Stop the director?"
      end
      facts
      button={(b) => (
        <button type="button" className="btn soft" disabled={busy} {...b}>
          <CircleStop size={14} strokeWidth={1.75} aria-hidden />
          Stop
        </button>
      )}
    >
      {(close) => (
        <div className="conf">
          <b>Stop the director?</b>
          <p>It makes no more moves. What it already started still finishes, and nothing is undone.</p>
          <div>
            <button type="button" className="btn soft" onClick={close}>
              Keep going
            </button>
            <button type="button" className="btn go" onClick={once(() => (close(), onStop()))}>
              Stop
            </button>
          </div>
        </div>
      )}
    </Popover>
  );
}

/** What the page offers under a run that isn't going (his Stop, or a run that ended): each press with its price when
 *  the server gives one, the first filled. `error`: the server's words for a press it refused. */
export function Offers({ presses, error }: { presses: Press[]; error: string | null }) {
  if (!presses.length && !error) return null;
  const why = presses.find((p) => p.why)?.why;
  return (
    <>
      <div className="offers">
        {presses.map((p, i) => (
          <PressButton key={p.label} press={p} kind={i ? "soft" : "go"} />
        ))}
      </div>
      {why && <p className="quiet small">{why}</p>}
      {error && <p role="alert">{error}</p>}
    </>
  );
}

/** His Stop, answered: what is kept, then Carry on and Start the plan again. */
export const Stopped = ({ stopped, presses, error }: { stopped: NonNullable<Progress["stopped"]>; presses: Press[]; error: string | null }) => (
  <>
    <p>{stoppedReply(stopped)}</p>
    <Offers presses={presses} error={error} />
  </>
);

/** A run that stopped by itself and needs him (a provider account that is empty, a step that failed twice), in the
 *  server's own words: what happened, what to do, and its ways on. Carry on and Try again are presses here; a fix that
 *  changes the video's settings or its plan is on the current site (`current`). */
export function Failed({ failed: f, projectId, carry, current }: { failed: NonNullable<Progress["failed"]>; projectId: number; carry: Press; current: string }) {
  const again = useTryAgain(projectId, f.clip);
  const priced = (price: string | null) => (!price ? undefined : price === "free" ? "free" : `up to ${price}`);
  return (
    <section className="ask" aria-label={f.title}>
      <p className="ask-h">
        <i aria-hidden className="dot bad" />
        The director needs you
      </p>
      <h3>{f.title}</h3>
      <p className="why">{f.why}</p>
      {f.offer && <p className="why">{f.offer}</p>}
      <div className="ask-f">
        {f.fixes.map((x, i) =>
          x.kind === "carry_on" ? (
            <PressButton key={x.kind} kind={i ? "soft" : "go"} press={{ ...carry, label: x.label, price: priced(x.price) }} />
          ) : x.kind === "again" ? (
            <PressButton key={x.kind} kind={i ? "soft" : "go"} press={{ label: x.label, price: priced(x.price), busy: again.isPending, onPress: () => again.mutate() }} />
          ) : (
            <Link key={x.kind} className="btn soft" to={`${current}?tab=plan`}>
              {x.label} on the current site
            </Link>
          ),
        )}
      </div>
      {carry.why && <p className="quiet small">{carry.why}</p>}
      {again.isError && <p role="alert">{again.error.message}</p>}
    </section>
  );
}
