import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Composer } from "../freestyle/Composer";
import { FromScript } from "../freestyle/FromScript";
import { Status } from "../freestyle/Thread";
import { SOON, sentTo, useFreestyles, type Freestyle } from "../freestyle/useFreestyle";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { useRail } from "../useMedia";

const day = (iso: string) => {
  const d = serverTime(iso);
  return d.toDateString() === new Date().toDateString() ? "today" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

/** New video (/b/:brandId/videos/new, v5 B_NewVideo): what the director should make, pasted or from a script
 *  (?from=script, E_PickInComposer). The owner's press makes it at once, an editor's goes to the owner; either way it
 *  lands on the video, where the director's chat is. */
export function NewVideoPage() {
  const brandId = Number(useParams().brandId);
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const owner = useMe().data?.role === "owner";
  const rail = useRail();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const fromScript = params.get("from") === "script";
  const onCreated = (fs: Freestyle) => navigate(sentTo(fs, owner, brandId));
  const toggle = (
    <div role="radiogroup" aria-label="Start from" className="flex rounded-md border border-border p-0.5 lg:inline-flex">
      {[
        ["", "Paste a script"],
        ["script", "From a script"],
      ].map(([id, label]) => (
        <button key={id} type="button" role="radio" aria-checked={(id === "script") === fromScript} onClick={() => setParams(id ? { from: id } : {}, { replace: true })} className={`min-h-control flex-1 whitespace-nowrap rounded-sm px-3 text-sm lg:min-h-[30px] ${(id === "script") === fromScript ? "bg-surface-2 font-medium text-text" : "text-muted hover:text-text"}`}>
          {label}
        </button>
      ))}
    </div>
  );
  return (
    <main className="flex min-h-[calc(100dvh-var(--tabbar-h))] flex-col lg:min-h-screen">
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 lg:min-h-[52px] lg:px-6">
        {fromScript || !rail ? (
          <h1 className="text-lg font-semibold">New video</h1>
        ) : (
          <p className="text-sm text-muted">
            {brand?.name} › <span className="font-medium text-text">New video</span>
          </p>
        )}
        {rail && toggle}
      </header>
      {!rail && <div className="px-4 pt-4">{toggle}</div>}
      {fromScript ? (
        <FromScript key={brandId} brandId={brandId} owner={owner} onCreated={onCreated} />
      ) : (
        <div className="mx-auto w-full max-w-[760px] space-y-4 px-4 pb-6 pt-4 lg:px-0 lg:pt-14">
          <div className="space-y-1">
            {rail && <h2 className="type-page">What should the director make?</h2>}
            <p className="text-sm text-muted">{rail ? "Paste a script or describe the video. The director plans it, casts it, makes the clips and cuts it." : "Paste a script or describe the video. The director makes it."}</p>
          </div>
          <Composer key={brandId} brandId={brandId} owner={owner} onCreated={onCreated} below={(typed) => (
            <>
              <p className="text-sm text-muted">{!typed ? SOON : owner ? "The director plans, casts, makes and cuts it. You can stop it any time." : "The owner approves it before anything is spent. You can withdraw it until then."}</p>
              {!typed && rail && <Recent brandId={brandId} owner={owner} />}
            </>
          )} />
        </div>
      )}
    </main>
  );
}

/** The newest few videos made this way (the owner sees everyone's), each with its status. */
function Recent({ brandId, owner }: { brandId: number; owner: boolean }) {
  const rows = useFreestyles(owner).data?.slice(0, 4) ?? [];
  if (!rows.length) return null;
  return (
    <section aria-label="Recent" className="pt-8">
      <div className="flex items-center justify-between pb-1.5">
        <h2 className="font-medium">Recent</h2>
        <Link to={`/b/${brandId}/videos`} className="text-sm text-muted hover:text-text">
          All videos
        </Link>
      </div>
      <ul>
        {rows.map((r) => (
          <li key={r.id} className="border-b border-border">
            <Link to={`/freestyle/${r.id}`} className="grid grid-cols-[minmax(0,1fr)_10rem_8rem] items-center gap-4 px-1 py-2.5 hover:bg-surface-2">
              <span className="truncate font-medium">{r.title}</span>
              <Status status={r.status} />
              <span className="text-right text-sm text-muted">{`${r.created_by_name} · ${day(r.created_at)}`}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
