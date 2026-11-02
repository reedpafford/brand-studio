import { useEffect, useRef, useState } from "react";
import { Download, Pencil, Plus, Square } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Button, Field, buttonClass, pressLabel } from "../components";
import { serverTime } from "../time";
import { Composer, useSettingsWords } from "./Composer";
import { Status, Thread } from "./Thread";
import { useFreestyle, useFreestyleActions, useFreestyles, type Freestyle } from "./useFreestyle";

const day = (iso: string) => {
  const d = serverTime(iso);
  return d.toDateString() === new Date().toDateString() ? "today" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

/** Freestyle (/freestyle, not under a brand; V3Freestyle board): your freestyles on the left, newest first; the open one's
 *  header, thread and composer on the right. /freestyle with no id is a new one. */
export function FreestylePage() {
  const raw = useParams().freestyleId;
  const id = raw ? Number(raw) : null;
  const navigate = useNavigate();
  const me = useMe().data;
  const owner = me?.role === "owner";
  const open = useFreestyle(id);
  const fs = open.data;
  const maker = !!fs && fs.created_by_name === me?.name;
  const words = useSettingsWords();
  const scroller = useRef<HTMLDivElement>(null);
  // Newest at the bottom: keep the latest move (and the delivered clip under it) in view as they arrive.
  useEffect(() => {
    scroller.current?.scrollTo?.({ top: scroller.current.scrollHeight });
  }, [fs?.thread.length, fs?.file_id]);
  return (
    <div className="lg:grid lg:min-h-screen lg:grid-cols-[260px_minmax(0,1fr)]">
      <List owner={owner} current={id} className={id ? "hidden lg:flex" : "flex"} />
      <main className="flex min-w-0 flex-col lg:h-screen">
        {id && (
          <Link to="/freestyle" className="flex min-h-control items-center self-start px-4 text-sm text-muted underline lg:hidden">
            All freestyles
          </Link>
        )}
        {fs && <Header fs={fs} maker={maker} />}
        <div ref={scroller} className="mx-auto w-full max-w-[760px] flex-1 space-y-6 overflow-y-auto p-4 lg:p-8">
          {id === null && <p className="text-sm text-muted">{owner ? "Your sends run at once." : "The owner approves every freestyle before anything is spent."}</p>}
          {open.isError && <p role="alert" className="text-danger">{open.error.message}</p>}
          {fs && <Thread fs={fs} tags={words(fs)} />}
          {fs?.file_id && (
            <video controls src={fileUrl(fs.file_id)} aria-label="The freestyle" className="mx-auto max-h-[50vh] w-full rounded-lg bg-surface-2 object-contain" style={{ aspectRatio: fs.shape.replace(":", " / ") }} />
          )}
        </div>
        <div className="mx-auto w-full max-w-[760px] px-4 pb-6 lg:px-8">
          {(id === null || fs) && <Composer key={id ?? "new"} fs={fs} owner={owner} maker={maker} onCreated={(n) => navigate(`/freestyle/${n}`)} />}
        </div>
      </main>
    </div>
  );
}

function List({ owner, current, className }: { owner: boolean; current: number | null; className: string }) {
  const [everyone, setEveryone] = useState(false);
  const rows = useFreestyles(owner && everyone);
  const seg = (on: boolean) => `min-h-control flex-1 rounded-md lg:min-h-control-dense px-2 text-sm ${on ? "bg-surface-3 font-medium" : "text-muted hover:bg-surface-2"}`;
  return (
    <aside aria-label="Your freestyles" className={`${className} min-w-0 flex-col border-border lg:sticky lg:top-0 lg:h-screen lg:border-r`}>
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h1 className="type-section">Freestyle</h1>
        <Link to="/freestyle" aria-label="New freestyle" title="New freestyle" className="grid size-control place-items-center rounded-md border border-border hover:bg-surface-2 lg:size-control-dense">
          <Plus size={16} strokeWidth={1.75} aria-hidden />
        </Link>
      </div>
      {owner && (
        <div role="group" aria-label="Whose" className="flex gap-1 p-2">
          <button type="button" aria-pressed={!everyone} className={seg(!everyone)} onClick={() => setEveryone(false)}>
            Mine
          </button>
          <button type="button" aria-pressed={everyone} className={seg(everyone)} onClick={() => setEveryone(true)}>
            Everyone's
          </button>
        </div>
      )}
      <ul className="flex flex-col gap-0.5 overflow-y-auto p-2">
        {rows.data?.length === 0 && <li className="px-2 py-1 text-sm text-muted">Nothing yet. Your freestyles show here.</li>}
        {rows.data?.map((r) => (
          <li key={r.id}>
            <Link to={`/freestyle/${r.id}`} aria-current={r.id === current ? "page" : undefined} className={`flex min-w-0 flex-col rounded-md px-2.5 py-2 ${r.id === current ? "bg-surface-2" : "hover:bg-surface-2"}`}>
              <span className="truncate text-sm font-medium">{r.title}</span>
              <Status status={r.status} tail={everyone ? `${day(r.created_at)} · ${r.created_by_name}` : day(r.created_at)} />
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function Header({ fs, maker }: { fs: Freestyle; maker: boolean }) {
  const actions = useFreestyleActions(fs.id);
  const [title, setTitle] = useState<string | null>(null);
  const error = [actions.rename, actions.stop, actions.withdraw].find((m) => m.isError)?.error?.message;
  const file = `${fs.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "freestyle"}.mp4`;
  return (
    <section aria-label="This freestyle" className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-3 lg:px-6">
      {title === null ? (
        <div className="flex min-w-0 items-center gap-1">
          <h2 className="truncate font-medium">{fs.title}</h2>
          <button type="button" aria-label="Rename" className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense" onClick={() => setTitle(fs.title)}>
            <Pencil size={16} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
      ) : (
        <form
          className="flex min-w-0 items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) actions.rename.mutate(title.trim(), { onSuccess: () => setTitle(null) });
          }}
        >
          <Field label="Title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} autoFocus />
          <Button type="submit" variant="secondary" busy={actions.rename.isPending}>Save</Button>
          <Button variant="ghost" onClick={() => setTitle(null)}>Cancel</Button>
        </form>
      )}
      <Status status={fs.status} />
      <span className="text-sm tabular-nums text-muted">{pressLabel(fs.credits, "estimate")}</span>
      <span className="flex-1" />
      {fs.status === "working" && (
        <Button variant="secondary" dense icon={Square} busy={actions.stop.isPending} onClick={() => actions.stop.mutate()}>
          Stop
        </Button>
      )}
      {fs.status === "waiting" && maker && (
        <Button variant="ghost" dense busy={actions.withdraw.isPending} onClick={() => actions.withdraw.mutate()}>
          Withdraw
        </Button>
      )}
      {fs.file_id && (
        <a className={buttonClass("secondary")} href={fileUrl(fs.file_id)} download={file}>
          <Download size={16} strokeWidth={1.75} aria-hidden />
          Download MP4
        </a>
      )}
      {error && <p role="alert" className="w-full text-sm text-danger">{error}</p>}
    </section>
  );
}
