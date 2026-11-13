import type { ReactNode } from "react";
import { fileUrl } from "../api/upload";
import { lookFitNote } from "../library/sheets";
import { said as price, type Ask } from "../videos/AskCard";
import { duration, plural } from "./script";
import { cameFrom, NOT_READY, once, type CastItem, type Planned, type Press } from "./videoData";

/** A press with its price riding on it, lighter than the verb. One press, one request: it is off while its request is
 *  in flight, and `why` (the server's own words for why it can't start) shows beside it. */
export function PressButton({ press, kind = "go" }: { press: Press; kind?: "go" | "soft" | "ghost" }) {
  return (
    <button type="button" className={`btn ${kind}`} disabled={press.busy || !!press.why} title={press.why ?? undefined} onClick={once(press.onPress)}>
      {press.label}{" "}
      {press.price && <small>{press.price}</small>}
    </button>
  );
}

/** The people and the places, each with where it comes from, a look still on its way, and its voice. */
function CastStrip({ cast }: { cast: CastItem[] }) {
  return (
    <ul className="cast-s" aria-label="The cast and places">
      {cast.map((i) => (
        <li key={i.ref}>
          {i.preview_file_id != null ? <img src={fileUrl(i.preview_file_id)} alt="" /> : <span aria-hidden className="im" />}
          <b>{i.name}</b>
          <small>{NOT_READY[i.readiness] ?? cameFrom(i)}</small>
          {i.voice && <small>Voice: {i.voice.name}</small>}
        </li>
      ))}
    </ul>
  );
}

/** What the look check says about a look, in its own words, before the press that accepts it. */
function Advice({ items, accepts }: { items: CastItem[]; accepts: string }) {
  if (!items.length) return null;
  return (
    <div className="advice" role="note">
      <ul>
        {items.map((i) => (
          <li key={i.ref}>
            <b>{i.name}.</b> {lookFitNote(i.look_fit!)}
          </li>
        ))}
      </ul>
      <p>{accepts}</p>
    </div>
  );
}

/** The start card (the server's start ask), as the director's proposal. The first one is the plan and the cast: who is
 *  in it and where each look comes from, what the look check says about any of them (the press accepts the looks as
 *  they stand), captions and time cards, and each clip the run makes with its price. After a delivery a note comes
 *  back as a round: only the clips it changes, each with its price. One press answers it, `press`; while the server
 *  is updating the plan for a note there is none and the card says so. `finish`: the two switches. */
export function StartCard({ ask: a, round, press, error, cast, plan, finish, onChange }: { ask: Ask; round: number; press: Press | null; error: string | null; cast: CastItem[]; plan: Planned[]; finish: ReactNode; onChange: () => void }) {
  const m = a.money;
  const making = m?.making ?? [];
  const again = round > 1;
  const row = (clip: string) => plan.find((c) => c.number === clip);
  return (
    <section className="ask" aria-label={again ? `Round ${round}` : "The plan and the cast"}>
      <p className="ask-h">
        <i aria-hidden className="dot wait" />
        {m?.updating ? "Updating the plan for your note…" : again ? "Ready when you are" : "Ready to start"}
      </p>
      <h3>{again && making.length ? `Round ${round}: ${plural(making.length, "clip")} change${making.length === 1 ? "s" : ""}` : a.question}</h3>
      <p className="why">{again ? "Everything else stays exactly as it is. The cut you have keeps playing until the new one is made." : a.why}</p>
      {!again && plan.length > 0 && (
        <p className="why">
          The plan is on the right: {plural(plan.length, "clip")}, about {duration(Math.round(plan.reduce((sum, c) => sum + c.seconds, 0)))}.
        </p>
      )}
      {!again && cast.length > 0 && <CastStrip cast={cast} />}
      {!again && <Advice items={cast.filter((i) => i.look_fit)} accepts="Approve and film uses these looks as they are. To change one, say so in the box below first." />}
      {!again && finish}
      {making.length > 0 && (
        <ul className={again ? "chg" : "chg all"} aria-label="What it will make">
          {making.map((c) => {
            const r = row(c.clip);
            return (
              <li key={c.clip}>
                {again && (r?.frame_file_id != null ? <img src={fileUrl(r.frame_file_id)} alt="" /> : <span aria-hidden className="im" />)}
                <span>
                  <b>{r?.name || `Clip ${c.clip}`}</b>
                  <small>{[r?.name && `Clip ${c.clip}`, `${c.seconds} s`].filter(Boolean).join(" · ")}</small>
                </span>
                <em>{price(c.price)}</em>
              </li>
            );
          })}
        </ul>
      )}
      <div className="ask-f">
        {press ? <PressButton press={press} /> : m?.updating && <p className="quiet small">The plan is being updated for your note. The press comes back with the new price.</p>}
        <button type="button" className="btn ghost" onClick={onChange}>
          {again ? "Change this plan…" : "Change the plan first…"}
        </button>
        {press && <small>Nothing is filmed until you press.</small>}
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

/** The cast waiting for its own OK (the server's cast gate): something changed the cast after the plan was approved.
 *  Who changed, the whole set as it now stands, and what the look check objects to. Its press approves the set exactly
 *  as shown; when the check objects, the press says "Approve anyway" and only then is `anyway` sent. */
export function CastCard({ cast, asked, press, error }: { cast: CastItem[]; asked: boolean; press: Press; error: string | null }) {
  const changed = cast.filter((i) => i.approval === "changed").map((i) => i.name);
  return (
    <section className="ask" aria-label="Cast and places waiting for your OK">
      <p className="ask-h">
        <i aria-hidden className="dot wait" />
        The director needs you
      </p>
      <h3>{changed.length ? `${changed.join(", ")} changed` : "The cast and places need your OK"}</h3>
      <p className="why">{asked ? "The director is waiting for this. " : ""}Check the cast and places together. Clips that use them wait until you approve.</p>
      <CastStrip cast={cast} />
      <Advice items={cast.filter((i) => i.approval !== "approved" && i.look_fit)} accepts="Approving anyway uses these looks as they are." />
      <div className="ask-f">
        <PressButton press={press} />
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
