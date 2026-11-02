import { useNavigate } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Panel, Skeleton, wholeCredits } from "../components";
import { SendPress } from "../freestyle/Composer";
import { HasVideo, mmss, useMakeFromScript } from "../freestyle/FromScript";
import { SHAPES, sentTo, type Freestyle } from "../freestyle/useFreestyle";
import { useBrands } from "../shell/useBrands";
import { lookName, useLooks } from "./Looks";
import { letterOf } from "./status";

/** Make a video from a script (E_ScriptMakeVideo): pick a version (each with its planned price) and a shape; the press
 *  sends it to the director: the owner's runs at once, an editor's goes to the owner. No Publish step first. */
export function MakeVideoPanel({ scriptId, onClose }: { scriptId: number; onClose: () => void }) {
  const owner = useMe().data?.role === "owner";
  const navigate = useNavigate();
  const looks = useLooks().data;
  const brands = useBrands().data;
  const sent = (fs: Freestyle) => navigate(sentTo(fs, owner, fs.brand_id ?? 0));
  const m = useMakeFromScript(scriptId, sent);
  const s = m.script;
  const footer = s && m.version && !m.video && (
    <>
      <p className="text-sm text-muted">{owner ? "The director plans, casts, makes and cuts it. You can stop it any time." : "The director plans, casts, makes and cuts it. The owner approves it before anything is spent."}</p>
      <SendPress owner={owner} price={m.price} busy={m.create.isPending} disabled={false} wide onClick={() => m.send()} />
      {m.error && <p role="alert" className="text-sm text-danger">{m.error}</p>}
    </>
  );
  return (
    <Panel wide title={s ? `Make a video from ${s.title}` : "Make a video"} onClose={onClose} footer={footer || undefined}>
      {!s ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="space-y-5">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted">Version</legend>
            {m.versions.map((v) => {
              const on = v.slot === m.version?.slot;
              return (
                <label key={v.slot} className={`flex min-h-control cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 ${on ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-2"}`}>
                  {/* The panel opens on the version picker, not Close (E_ScriptMakeVideo): marked for the overlay, or focused once loaded. */}
                  <input type="radio" name="version" checked={on} onChange={() => m.pick(v.slot)} data-autofocus={on || undefined} autoFocus={on} className="size-4 accent-(--accent)" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{letterOf(v.slot)}</span>
                    <span className="block text-sm text-muted">{[v.seconds > 0 && mmss(v.seconds), v.project_id && "has a video"].filter(Boolean).join(" · ")}</span>
                  </span>
                  {v.estimate_credits > 0 && <span className={`text-sm tabular-nums ${on ? "text-accent-text" : "text-muted"}`}>{`about ${wholeCredits(v.estimate_credits)} credits (planned)`}</span>}
                </label>
              );
            })}
          </fieldset>
          <div className="space-y-2">
            <p className="text-sm text-muted">Shape</p>
            <div role="radiogroup" aria-label="Shape" className="inline-flex rounded-md border border-border p-0.5">
              {SHAPES.map((x) => (
                <button key={x} type="button" role="radio" aria-checked={x === m.shape} onClick={() => m.setShape(x)} className={`min-h-control rounded-sm px-3 text-sm lg:min-h-control-dense ${x === m.shape ? "bg-surface-2 font-medium" : "text-muted hover:text-text"}`}>
                  {x}
                </button>
              ))}
            </div>
          </div>
          <p className="flex flex-wrap gap-x-4 text-sm text-muted">
            <span>
              Type <span className="text-text">Dialogue</span>
            </span>
            <span>
              Style <span className="text-text">{lookName(looks, s.look)}</span>
            </span>
            <span>
              Brand <span className="text-text">{brands?.find((b) => b.id === s.brand_id)?.name}</span>
            </span>
          </p>
          {m.video && <HasVideo m={m} brandId={s.brand_id} />}
        </div>
      )}
    </Panel>
  );
}
