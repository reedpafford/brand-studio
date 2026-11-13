import { useRef, useState, type ReactNode } from "react";
import { LoaderCircle, MessageSquare, Pause, Play, Sparkles, Upload } from "lucide-react";
import { fileUrl } from "../api/upload";
import { isOpen, said as price, useAskActions, useAskUpload, type Ask } from "../videos/AskCard";
import { once } from "./videoData";

const ICON = { size: 14, strokeWidth: 1.75, "aria-hidden": true } as const;
type Voice = { id: string; name: string; note?: string; state?: string; sample_file_id?: number | null; sample_url?: string | null };
/** What a card's options are called, as the current site calls them. */
const NOUN: Record<string, string> = { cast: "looks", presenter: "avatars", place: "places", voice: "voices" };

/** One voice: hear it (what it read of the script, or its sample), then use it. */
function VoiceRow({ v, use, busy, onUse }: { v: Voice; use: boolean; busy: boolean; onUse: () => void }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const src = v.sample_file_id != null ? fileUrl(v.sample_file_id) : v.sample_url ? `/api${v.sample_url}` : null;
  const reading = !src && ["queued", "running"].includes(v.state ?? "");
  return (
    <li className="vrow">
      <button type="button" className="btn soft square" disabled={!src} aria-label={`${playing ? "Pause" : "Play"} ${v.name}`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))}>
        {reading ? <LoaderCircle {...ICON} className="spin" /> : playing ? <Pause {...ICON} /> : <Play {...ICON} />}
        {src && <audio ref={audio} src={src} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />}
      </button>
      <span>
        <b>{v.name}</b>
        <small>{src || !v.state ? v.note : reading ? "Reading your script…" : "Didn’t read. Nothing was charged."}</small>
      </span>
      {use && (
        <button type="button" className="btn ghost" disabled={busy} aria-label={`Use ${v.name}`} onClick={once(onUse)}>
          Use
        </button>
      )}
    </li>
  );
}

/** A way to answer that isn't a saved item: its name and one line under it. */
const Way = ({ icon, title, note, busy, onPress }: { icon: ReactNode; title: string; note: string; busy?: boolean; onPress: () => void }) => (
  <button type="button" className="way" disabled={busy} onClick={once(onPress)}>
    {icon}
    <span>
      <b>{title}</b> <small>{note}</small>
    </span>
  </button>
);

/** A card the director asks with, in the new look, with the same answers the current site's card posts: someone or
 *  something saved in the brand (names first, the picture only for the one picked), the options it drew, drawing some
 *  (its price first), an upload, a reply in words, a voice from its audition, a story's choice, or a money card's yes or
 *  no. One press, one request: every press is off while one is in flight. One answered or no longer needed is a line. */
export function Question({ ask: a }: { ask: Ask }) {
  const act = useAskActions(a);
  const [pick, setPick] = useState<string | number | null>(null);
  const [typing, setTyping] = useState<"" | "reply" | "change">("");
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const picker = useRef<HTMLInputElement>(null);
  const up = useAskUpload(a, act);
  if (!isOpen(a))
    return (
      <p className="folded">
        <b>{a.question}</b>
        <small>{a.state === "not_needed" ? `No longer needed. ${a.closed}` : a.answered_by ? `Answered by ${a.answered_by}` : "Answered"}</small>
      </p>
    );
  const can = (how: string) => a.can.includes(how);
  const busy = act.isPending || !!up.upload;
  const go = (body: object, path?: "generate" | "cancel") => act.mutate({ path, body }, { onSuccess: () => (setTyping(""), setText(""), setName(""), setPick(null), up.clear()) });
  const voice = a.kind === "voice";
  const drawn = a.options.filter((o) => o.file_id != null);
  const options = a.options.length > 0 && a.state !== "failed";
  const chosen = pick ?? (options ? (drawn[0]?.index ?? null) : null);
  const saved = a.saved.find((o) => o.id === chosen);
  const noun = NOUN[a.kind] ?? "options";
  const upTo = (p: Ask["generate"]) => (p ? ` · up to ${price(p)}` : "");
  const audition = a.audition.length > 0 && !a.voice;
  const error = up.failed || (act.isError ? act.error.message : "");

  return (
    <section className="ask" id={`ask-${a.id}`} aria-label={a.question}>
      <input ref={picker} type="file" hidden accept={voice ? "audio/*" : "image/*,video/*"} aria-label={voice ? "Upload a voice sample" : "Upload a photo, a still or a clip"} onChange={(e) => (void up.send(e.target.files), (e.target.value = ""))} />
      <p className="ask-h">
        <i aria-hidden className="dot wait" />
        The director needs you
      </p>
      <h3>{a.question}</h3>
      {a.why && <p className="why">{a.why}</p>}

      {a.money && a.kind !== "start" ? (
        <div className="ask-f">
          {can("approve") && (
            <button type="button" className="btn go" disabled={busy} onClick={once(() => go({ how: "approve" }))}>
              Approve <small>up to {price(a.money.up_to)} more</small>
            </button>
          )}
          {can("keep") && (
            <button type="button" className="btn soft" disabled={busy} onClick={once(() => go({ how: "keep" }))}>
              {a.kind === "budget" ? "Keep the cut as it is" : a.kind === "plan" ? "Keep the plan" : "Stop here"}
            </button>
          )}
        </div>
      ) : up.upload || a.state === "uploading" ? (
        <p className="quiet small" role="status">
          Uploading {up.upload?.name ?? "your file"}, for this video only…
        </p>
      ) : a.state === "generating" ? (
        <div className="ask-f">
          <p className="quiet small" role="status">
            <LoaderCircle {...ICON} className="spin" /> {voice ? `Cloning the voice${upTo(a.clone)}` : `Drawing 3 ${noun}${upTo(a.generate)}`}
          </p>
          {can("cancel") && !voice && (
            <button type="button" className="btn ghost" disabled={busy} onClick={once(() => go({}, "cancel"))}>
              Cancel
            </button>
          )}
        </div>
      ) : a.kind === "story" && a.choices.length > 0 ? (
        <>
          <ul className="picks">
            {a.choices.map((c) => (
              <li key={c.key}>
                <small>{a.pick === c.key ? `${c.key} · the director’s pick` : c.key}</small>
                <b>{c.title}</b>
                <span>{c.why}</span>
              </li>
            ))}
          </ul>
          <div className="ask-f">
            {a.choices.map((c, i) => (
              <button key={c.key} type="button" className={i ? "btn soft" : "btn go"} disabled={busy} onClick={once(() => go({ how: "choice", choice: c.key }))}>
                Go with {c.key}
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          {audition && (
            <>
              <h4>Hear them read your script, then pick {a.subject || "the presenter"}’s voice</h4>
              <ul>
                {a.audition.map((v) => (
                  <VoiceRow key={v.id} v={v} use={can("voice") && (v.sample_file_id != null || a.audition_failed)} busy={busy} onUse={() => go({ how: "voice", option: v.id })} />
                ))}
              </ul>
              {a.audition_failed && (
                <div className="ask-f">
                  <p className="quiet small">None of them read. Nothing was charged.</p>
                  {can("again") && (
                    <button type="button" className="btn soft" disabled={busy} onClick={once(() => go({ how: "again" }))}>
                      Read them again
                    </button>
                  )}
                </div>
              )}
              {a.audition_failed && a.other_voices.length > 0 && (
                <ul>
                  {a.other_voices.map((v) => (
                    <VoiceRow key={v.id} v={v} use={can("voice")} busy={busy} onUse={() => go({ how: "voice", option: v.id })} />
                  ))}
                </ul>
              )}
            </>
          )}
          {a.state === "failed" && <p className="why">{voice ? "The voice didn’t clone. Nothing was charged." : "The picture service made nothing. Nothing was charged."}</p>}
          {options ? (
            <>
              <h4>Made for this video · not saved to the brand</h4>
              <div className="opts">
                {a.options.map((o) => (
                  <button key={o.index} type="button" className="opt" disabled={o.file_id == null} aria-pressed={chosen === o.index} onClick={() => setPick(o.index)}>
                    <span className="im">{o.file_id != null && <img src={fileUrl(o.file_id)} alt="" />}</span>
                    <b>Option {o.index + 1}</b>
                    {o.file_id == null && <small>{o.state === "failed" ? "didn’t draw" : "drawing…"}</small>}
                  </button>
                ))}
              </div>
            </>
          ) : (
            a.saved.length > 0 &&
            (voice ? (
              <>
                <h4>{a.saved_in || "Saved voices"}</h4>
                <ul>
                  {a.saved.map((o) => (
                    <VoiceRow key={o.id} v={o} use={can("saved")} busy={busy} onUse={() => go({ how: "saved", option: o.id })} />
                  ))}
                </ul>
              </>
            ) : (
              <>
                <h4>{a.saved_in || "Saved"}</h4>
                <div className="names">
                  {a.saved.map((o) => (
                    <button key={o.id} type="button" className="pill" aria-pressed={chosen === o.id} onClick={() => setPick(o.id)}>
                      {o.name}
                    </button>
                  ))}
                </div>
                {saved && (
                  <div className="prev">
                    {saved.file_id != null && <img src={fileUrl(saved.file_id)} alt="" />}
                    <span>
                      <b>{saved.name}</b>
                      <small>{[saved.note, saved.used_in ? `in ${saved.used_in} video${saved.used_in === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ")}</small>
                    </span>
                    {can("saved") && (
                      <button type="button" className="btn go" disabled={busy} onClick={once(() => go({ how: "saved", option: saved.id }))}>
                        Use {saved.name}
                      </button>
                    )}
                  </div>
                )}
              </>
            ))
          )}
          {options && drawn.length > 0 ? (
            <div className="ask-f">
              {typeof chosen === "number" && can("option") && (
                <button type="button" className="btn go" disabled={busy} onClick={once(() => go({ how: "option", option: chosen }))}>
                  Use option {chosen + 1}
                </button>
              )}
              {typeof chosen === "number" && can("generate") && (
                <button type="button" className="btn soft" disabled={busy} onClick={once(() => go({ like: chosen }, "generate"))}>
                  More like {chosen + 1}{" "}
                  {a.generate && <small>up to {price(a.generate)}</small>}
                </button>
              )}
              {can("generate") && (
                <button type="button" className="btn ghost" aria-expanded={typing === "change"} onClick={() => setTyping(typing === "change" ? "" : "change")}>
                  Change something…
                </button>
              )}
              {a.options_spent && a.options_spent.credits > 0 && <small>{price(a.options_spent)} spent</small>}
            </div>
          ) : (
            (can("upload") || can("clone") || can("reply") || can("describe") || can("generate")) && (
              <>
                {(a.saved.length > 0 || audition) && <h4>{voice ? "Other ways" : "Or someone new"}</h4>}
                <div className="ways">
                  {can("generate") && a.generate && <Way icon={<Sparkles {...ICON} />} title={a.state === "failed" ? "Try again" : `Draw 3 ${noun}`} note={`Up to ${price(a.generate)} · for this video only`} busy={busy} onPress={() => go({}, "generate")} />}
                  {can("upload") && !voice && <Way icon={<Upload {...ICON} />} title="Upload" note="A photo, a still or a clip" busy={busy} onPress={() => picker.current?.click()} />}
                  {can("clone") && <Way icon={<Upload {...ICON} />} title="Upload a sample" note={`Cloned once${upTo(a.clone)} · ${(a.clone_to || "saved to the brand’s voices").replace(/^Saved/, "saved")}`} busy={busy} onPress={() => picker.current?.click()} />}
                  {(can("reply") || can("describe")) && <Way icon={<MessageSquare {...ICON} />} title={voice ? "Describe it" : "Tell me in words"} note={voice ? "“Late 40s, tired, warm”" : "Answer in a line or two"} onPress={() => setTyping(typing === "reply" ? "" : "reply")} />}
                </div>
              </>
            )
          )}
          {typing && (
            <form
              className="reply"
              onSubmit={(e) => {
                e.preventDefault();
                const t = text.trim();
                if (!t || busy) return;
                if (typing === "change") go({ change: t }, "generate");
                else go(voice ? { how: "describe", text: t, name: name.trim() } : { how: "reply", text: t });
              }}
            >
              <textarea rows={2} value={text} autoFocus aria-label={typing === "change" ? "What should change" : voice ? "What the voice sounds like" : "Your answer"} placeholder={typing === "change" ? "What should change?" : voice ? "Late 40s, tired, warm" : "Tell me in words"} onChange={(e) => setText(e.target.value)} />
              {voice && typing === "reply" && <input value={name} maxLength={120} aria-label="Its name (optional)" placeholder="Its name (optional)" onChange={(e) => setName(e.target.value)} />}
              <div className="ask-f">
                <button type="submit" className="btn go" disabled={busy || !text.trim()}>
                  {typing === "change" ? "Make 3 more" : voice ? "Save and use it" : "Send the answer"}{" "}
                  {typing === "change" && a.generate && <small>up to {price(a.generate)}</small>}
                </button>
                <button type="button" className="btn ghost" onClick={() => setTyping("")}>
                  Not now
                </button>
              </div>
            </form>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
