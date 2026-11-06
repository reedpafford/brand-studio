import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FileText, Film, Inbox, MessageSquare } from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Banner, Button, buttonClass, EmptyState, Skeleton, useToast } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { serverTime } from "../time";
import { useRail } from "../useMedia";

type Out = components["schemas"]["NeedsYouOut"];
type Row = components["schemas"]["NeedsYouRow"];
type Send = components["schemas"]["HeldSend"];
type Stuck = components["schemas"]["StuckVideo"];
type Price = components["schemas"]["AskPrice"];

/** GET /needs-you: the owner's one inbox across brands (questions, money, stuck), with every brand's count. `brand`
 *  filters the lists; the counts stay whole. The rail and the phone tab read its total. */
export function useNeedsYou(brand: number | null = null, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["needs-you", brand ?? "all"],
    refetchInterval: 30_000,
    queryFn: async () => {
      const { data, error } = await api.GET("/needs-you", { params: { query: brand ? { brand_id: brand } : {} } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
  });
}

const said = (p: Price) => (p.usd != null ? `$${p.usd.toFixed(2)}` : `${Math.ceil(p.credits)} credit${Math.ceil(p.credits) === 1 ? "" : "s"}`);
const chat = (brand: number, video: number, tab?: string) => `/b/${brand}/videos/${video}${tab ? `?tab=${tab}` : ""}`;

/** "12 min", "1 h", "2 days": how long it has waited. */
function waited(iso: string) {
  const s = Math.max(0, (Date.now() - serverTime(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h`;
  const days = Math.floor(s / 86400);
  return `${days} day${days === 1 ? "" : "s"}`;
}

/** Ask Needs you, the video's chat and the jobs again after a press: an answer here is the same answer as there. */
function useAfter() {
  const queryClient = useQueryClient();
  return () => Promise.all([refreshJobs(queryClient), ...["needs-you", "asks", "ideas", "run-progress", "director"].map((k) => queryClient.invalidateQueries({ queryKey: [k] }))]);
}

/** One press on a card: it runs, the lists are read again, and a failure says why under the card. */
function usePress(done: string) {
  const toast = useToast();
  const after = useAfter();
  return useMutation({
    mutationFn: async (go: () => Promise<{ error?: unknown; response: Response }>) => {
      const { error, response } = await go();
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await after();
      toast(done);
    },
  });
}

const answer = (ask: number, body: components["schemas"]["AnswerIn"]) => () => api.POST("/asks/{ask_id}/answer", { params: { path: { ask_id: ask } }, body });

/** A press's label with its 14 px icon, as the board's buttons draw them. */
const Label = ({ icon: Icon, children }: { icon?: typeof Check; children: ReactNode }) => (
  <span className="inline-flex items-center gap-1.5">
    {Icon && <Icon size={14} strokeWidth={1.75} aria-hidden />}
    {children}
  </span>
);

/** The idea's still (or a quiet placeholder before anything is drawn). */
function Still({ id, phone }: { id: number | null | undefined; phone: boolean }) {
  const size = phone ? "h-[78px] w-[44px]" : "h-[96px] w-[54px]";
  return (
    <span aria-hidden className={`${size} grid shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-faint`}>
      {id ? <img src={fileUrl(id)} alt="" className="size-full object-cover" /> : <Film size={16} strokeWidth={1.75} />}
    </span>
  );
}

/** One card (S9-01's item, P-14's on a phone): the still, the idea and its brand with how long it has waited, the
 *  question or what it needs, a line of detail (computer only), then its presses. */
function Card({ id, still, idea, brand, when, title, line, error, children, phone, mark }: { id?: string; still: number | null | undefined; idea: string; brand?: string; when: string; title: string; line?: string; error?: string | null; children: ReactNode; phone: boolean; mark?: boolean }) {
  return (
    <li id={id} tabIndex={mark ? -1 : undefined} className={`flex items-start rounded-lg border border-border bg-surface ${phone ? "gap-3 p-3" : "gap-3.5 px-4 py-3.5"} ${mark ? "outline outline-2 -outline-offset-2 outline-accent" : ""}`}>
      <Still id={still} phone={phone} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {phone ? (
          <span className="text-xs text-muted">{[idea, brand].filter(Boolean).join(" · ")}</span>
        ) : (
          <span className="flex items-baseline gap-2 text-[13px] leading-[18px]">
            <span className="font-semibold">{idea}</span>
            {brand && <span className="text-muted">· {brand}</span>}
            <span className="flex-1" />
            <span className="shrink-0 text-xs text-muted">{when}</span>
          </span>
        )}
        <h3 className={phone ? "text-[13px] font-semibold leading-[18px]" : "text-[15px] font-semibold leading-[22px]"}>{title}</h3>
        {!phone && line && <p className="text-[13px] leading-[18px] text-muted">{line}</p>}
        {children}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </li>
  );
}

// P-14's presses are 14 px with 12 px sides, so a card's two fit across 390; they stay 44 px tall to touch.
const Presses = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap gap-2 max-lg:[&>*]:px-3! max-lg:[&>*]:text-sm">{children}</div>;
const OpenChat = ({ to, phone, name }: { to: string; phone: boolean; name: string }) => (
  <Link to={to} className={buttonClass("secondary")} aria-label={`Open the chat: ${name}`}>
    {phone ? "Open" : <Label icon={MessageSquare}>Open the chat</Label>}
  </Link>
);

/** The idea as the card names it: an editor's send not yet OK'd says whose ("Gut check (Kel's send)"). */
const idea = (v: Row["video"], phone: boolean) => (v.send ? (phone ? `${v.title}, ${v.made_by}’s send` : `${v.title} (${v.made_by}’s send)`) : v.title);

/** A question from the director: the brand's saved items (the director's pick outlined), a story's choices, or the
 *  options made for it; Use / Go with answers it here, the same answer as in the chat (S4-01, S4-02). */
function Question({ row, phone }: { row: Row; phone: boolean }) {
  const a = row.ask;
  const press = usePress("Answered. The director carries on.");
  const pictures = [...a.saved].sort((x, y) => Number(y.id === a.pick) - Number(x.id === a.pick)).slice(0, 4); // the pick first
  const story = a.kind === "story" ? a.choices : [];
  const first = story.length ? (a.pick ?? null) : a.options.length ? null : (pictures.find((o) => o.id === a.pick)?.id ?? null); // options made: picked in the chat
  const [picked, setPicked] = useState<string | null>(first);
  const option = pictures.find((o) => o.id === picked);
  const can = (how: string) => a.can.includes(how);
  const use = story.length && picked && can("choice")
    ? { label: `Go with ${picked}`, body: { how: "choice", choice: picked } }
    : option && can("saved")
      ? { label: `Use ${option.name}`, body: { how: "saved", option: option.id } }
      : null;
  const pick = (id: string, name: string, on: boolean, child: ReactNode, wide?: boolean) => (
    <button key={id} type="button" aria-pressed={on} aria-label={name} onClick={() => setPicked(id)}
      className={`overflow-hidden rounded-md ${wide ? "border border-border px-2.5 py-1.5 text-left text-[13px]" : ""} ${on ? "outline outline-2 outline-offset-2 outline-accent" : ""}`}>
      {child}
    </button>
  );
  return (
    <Card still={row.video.still_file_id} idea={idea(row.video, phone)} brand={row.brand.name} when={waited(a.created_at)} title={a.question} line={a.why} error={press.isError ? press.error.message : null} phone={phone}>
      {!phone && (pictures.length > 0 || story.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {story.map((c) => pick(c.key, `${c.key}: ${c.title}`, picked === c.key, <span><b>{c.key}</b>{a.pick === c.key && " · my pick"} · {c.title}</span>, true))}
          {pictures.map((o) => pick(o.id, o.name, picked === o.id, o.file_id ? <img src={fileUrl(o.file_id)} alt="" className="h-[86px] w-[64px] object-cover" /> : <span className="block px-2.5 py-1.5 text-[13px]">{o.name}</span>, !o.file_id))}
        </div>
      )}
      <Presses>
        {use && (
          <Button variant="secondary" busy={press.isPending} onClick={() => press.mutate(answer(a.id, use.body))}>
            <Label icon={Check}>{use.label}</Label>
          </Button>
        )}
        <OpenChat to={chat(row.brand.id, row.video.id)} phone={phone} name={row.video.title} />
      </Presses>
    </Card>
  );
}

/** A money card (S3-02, S3-06, S4-02): past the budget, the director's own limit, planning, or the start of an editor's
 *  send. The first money card's approval is the screen's one indigo press (review.md 12). */
function Money({ row, phone, main, me }: { row: Row; phone: boolean; main: boolean; me: string }) {
  const a = row.ask;
  const m = a.money!;
  const press = usePress("Done. Nothing more waits on this.");
  const up = said(m.up_to);
  const name = row.video.title;
  const can = (how: string) => a.can.includes(how);
  const go = (how: string) => () => press.mutate(answer(a.id, { how }));
  let title = a.question;
  let line = a.why;
  let yes: ReactNode = null;
  let no: ReactNode = null;
  let third: ReactNode = <OpenChat to={chat(row.brand.id, row.video.id)} phone={phone} name={name} />;
  if (a.kind === "start") {
    const theirs = row.video.made_by && can("decline"); // an editor's send: the owner starts it
    title = theirs ? (phone ? `Start it · up to ${up}` : `${row.video.made_by}’s new video · up to ${up}`) : `Make it for up to ${up}?`;
    line = theirs ? `${row.video.about ? `${row.video.about}. ` : ""}Nothing is spent until you approve.` : a.why;
    if (can("make_it"))
      yes = (
        <Button variant={main ? "primary" : "secondary"} busy={press.isPending} onClick={go("make_it")}>
          <Label icon={Check}>{theirs ? (phone ? `Approve · up to ${up}` : "Approve and start") : `Make it · up to ${up}`}</Label>
        </Button>
      );
    if (can("decline")) no = <Button variant="secondary" disabled={press.isPending} onClick={go("decline")}>Decline</Button>;
    if (theirs) third = phone ? null : <Link to={chat(row.brand.id, row.video.id, "script")} className={buttonClass("secondary")} aria-label={`Read the script: ${name}`}><Label icon={FileText}>Read the script</Label></Link>;
  } else {
    if (a.kind === "budget" && m.past) {
      const clips = m.what.match(/^(Redo|Make) clips /) && m.clips.length > 1 ? `${m.what.split(" ")[0]} ${m.clips.length} clips` : m.what;
      const over = phone && m.over !== "the budget" ? "this run’s price" : m.over; // a later run's own price (rule 34), shorter on a phone
      title = `${phone ? clips : m.what} · ${said(m.past)} past ${over}`;
      line = `${row.video.made_by && row.video.made_by !== me ? `${row.video.made_by}’s video. ` : ""}${a.why}`;
    }
    if (can("approve"))
      yes = (
        <Button variant={main ? "primary" : "secondary"} busy={press.isPending} onClick={go("approve")}>
          <Label icon={Check}>{`Approve · up to ${up}${phone ? "" : " more"}`}</Label>
        </Button>
      );
    if (can("keep")) no = <Button variant="secondary" disabled={press.isPending} onClick={go("keep")}>Decline</Button>;
    if (phone) third = null;
  }
  return (
    <Card still={row.video.still_file_id} idea={idea(row.video, phone)} brand={row.brand.name} when={waited(m.sent_at)} title={title} line={line} error={press.isError ? press.error.message : null} phone={phone}>
      <Presses>
        {yes}
        {no}
        {third}
      </Presses>
    </Card>
  );
}

/** A press held outside any video (a script's songs or narration, an editor's Quick clip): Approve or Decline. */
function HeldSend({ send: s, phone, main, mark }: { send: Send; phone: boolean; main: boolean; mark: boolean }) {
  const press = usePress("Done. Nothing more waits on this.");
  const up = said(s.up_to);
  const path = { params: { path: { job_id: s.job_id } } };
  useEffect(() => {
    if (!mark) return;
    const row = document.getElementById(`job-${s.job_id}`);
    row?.scrollIntoView?.({ block: "center" });
    row?.focus();
  }, [mark, s.job_id]);
  return (
    <Card id={`job-${s.job_id}`} mark={mark} still={null} idea={`${s.made_by}’s request`} brand={s.brand?.name} when={waited(s.at)} title={`${s.what} · up to ${up}`} line={s.held} error={press.isError ? press.error.message : null} phone={phone}>
      <Presses>
        <Button variant={main ? "primary" : "secondary"} busy={press.isPending} onClick={() => press.mutate(() => api.POST("/jobs/{job_id}/approve", path))}>
          <Label icon={Check}>{`Approve · up to ${up}`}</Label>
        </Button>
        <Button variant="secondary" disabled={press.isPending} onClick={() => press.mutate(() => api.POST("/jobs/{job_id}/decline", { ...path, body: { reason: "" } }))}>
          Decline
        </Button>
        {!phone && s.script_id != null && s.brand && (
          <Link to={`/b/${s.brand.id}/scripts/${s.script_id}`} className={buttonClass("secondary")}>
            <Label icon={FileText}>Read the script</Label>
          </Link>
        )}
      </Presses>
    </Card>
  );
}

/** A stuck video (rule 22): what went wrong and why, and its one-click fix, the same press and price as its own stuck
 *  card in the chat (S3-11). */
function StuckRow({ row, phone }: { row: Stuck; phone: boolean }) {
  const f = row.fix;
  const press = usePress(f.kind === "split" ? "Split. The words don’t change." : "Started again.");
  const pid = { project_id: row.video.id };
  const run: Record<string, (() => () => Promise<{ error?: unknown; response: Response }>) | undefined> = {
    again: () => () => api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path: { ...pid, clip_id: f.clip_id ?? 0 } } }),
    redraw: () => () => api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/render", { params: { path: { ...pid, frame_id: f.frame_id ?? 0 } } }),
    carry_on: () => () => api.POST("/projects/{project_id}/director", { params: { path: pid } }),
    split: () => () => api.POST("/projects/{project_id}/breakdown/fix", { params: { path: pid }, body: { problems: f.problem ? [f.problem] : [] } }),
  };
  const does = run[f.kind];
  const price = f.price ? (f.price === "free" ? " · free" : ` · up to ${f.price}`) : "";
  const open = chat(row.brand.id, row.video.id, f.kind === "model" ? "plan" : undefined);
  return (
    <Card still={row.video.still_file_id} idea={idea(row.video, phone)} brand={row.brand.name} when={waited(row.at)} title={row.what} line={row.why} error={press.isError ? press.error.message : null} phone={phone}>
      <Presses>
        {does ? (
          <Button variant="secondary" busy={press.isPending} onClick={() => press.mutate(does())}>
            <Label icon={Check}>{`${f.label}${price}`}</Label>
          </Button>
        ) : (
          <Link to={open} className={buttonClass("secondary")}>
            {f.kind === "chat" ? <Label icon={MessageSquare}>Open the chat</Label> : f.label}
          </Link>
        )}
        {does && !phone && <OpenChat to={open} phone={phone} name={row.video.title} />}
      </Presses>
    </Card>
  );
}

/** A computer's section, its title over its cards; a phone lists every card in one run (P-14 has no titles). */
const Section = ({ title, phone, children }: { title: string; phone: boolean; children: ReactNode }) => (
  <section aria-label={title} className={`flex flex-col ${phone ? "gap-3" : "gap-4"}`}>
    {!phone && <h2 className="text-[13px] font-semibold leading-[18px]">{title}</h2>}
    <ul className={`flex flex-col ${phone ? "gap-3" : "gap-4"}`}>{children}</ul>
  </section>
);

/** Needs you (S9-01, P-14): the owner's one inbox across brands. Questions from the director, money OKs and stuck
 *  videos, each with its press; answering here is the same answer as in the video's chat. Editors have My requests. */
export function NeedsYouPage() {
  const { data: me } = useMe();
  const owner = me?.role === "owner";
  const phone = !useRail();
  const [params, setParams] = useSearchParams();
  const brand = phone ? null : Number(params.get("brand")) || null;
  const q = useNeedsYou(brand, owner);
  const job = Number(params.get("job")) || null;
  if (me && !owner) return <Navigate to="/requests" replace />; // an editor's own sends are in My requests (S-gaps-04 R4)
  const pad = phone ? "p-3.5" : "px-6 py-6";
  if (!me || q.isPending)
    return (
      <main className={`mx-auto w-full max-w-[860px] space-y-4 ${pad}`} aria-label="Loading">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </main>
    );
  if (q.isError || !q.data)
    return (
      <main className={`mx-auto w-full max-w-[860px] ${pad}`}>
        <Banner title="Couldn’t load what needs you." action={<Button variant="secondary" onClick={() => void q.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      </main>
    );
  const d: Out = q.data;
  const shown = d.questions.length + d.money.length + d.sends.length + d.stuck.length;
  const first = d.money.find((r) => r.ask.can.some((c) => c === "approve" || c === "make_it"));
  const main = first ? `ask-${first.ask.id}` : d.sends[0] ? `job-${d.sends[0].job_id}` : null; // the one indigo press
  const named = d.brands.find((b) => b.id === brand)?.name;
  const filter = (
    <div role="radiogroup" aria-label="Brand" className="inline-flex gap-0.5 rounded-md bg-surface-2 p-0.5">
      {[{ id: null as number | null, label: "All brands", count: null as number | null }, ...d.brands.map((b) => ({ id: b.id as number | null, label: b.name, count: b.count as number | null }))].map((b) => (
        <button key={b.id ?? "all"} type="button" role="radio" aria-checked={brand === b.id} onClick={() => setParams(b.id ? { brand: String(b.id) } : {}, { replace: true })}
          className={`inline-flex h-7 items-center gap-1.5 rounded-[5px] px-3 text-[13px] font-medium ${brand === b.id ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"}`}>
          {b.label}
          {b.count !== null && <span className="tabular-nums">{b.count}</span>}
        </button>
      ))}
    </div>
  );
  return (
    <div className="flex min-h-full flex-col">
      {!phone && (
        <header className="flex h-[52px] shrink-0 items-center border-b border-border bg-surface px-5 text-[13px] font-semibold">Needs you</header>
      )}
      {phone && (
        // P-14's header: the title and its line over a hairline, above the list.
        <header className="flex shrink-0 flex-col border-b border-border bg-surface px-3.5 pb-2.5 pt-3">
          <h1 className="text-[15px] font-semibold leading-[22px]">Needs you</h1>
          <p className="text-xs text-muted">{d.total} waiting · every brand</p>
        </header>
      )}
      <main className={`mx-auto flex w-full flex-col ${phone ? "gap-3 p-3.5" : "max-w-[908px] gap-4 px-6 py-6"}`}>
        {phone ? null : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-[22px] font-semibold leading-[30px] tracking-[-0.012em]">Needs you</h1>
              <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-warning-soft px-1.5 text-[11px] font-semibold text-warning tabular-nums">
                {d.total}
                <span className="sr-only"> waiting</span>
              </span>
              <span className="flex-1" />
              {d.brands.length > 0 && filter}
            </div>
            <p className="text-[13px] leading-[18px] text-muted">Questions from the director, budget OKs and stuck videos, across every brand. Answer here or in the video’s chat; it’s the same answer.</p>
          </>
        )}
        {shown === 0 ? (
          <EmptyState icon={Inbox} title={named ? `Nothing needs you in ${named}.` : "Nothing needs you."}>
            The director’s questions, budget OKs and stuck videos show here, across every brand.
          </EmptyState>
        ) : (
          <>
            {d.questions.length > 0 && <Section title="Questions" phone={phone}>{d.questions.map((r) => <Question key={r.ask.id} row={r} phone={phone} />)}</Section>}
            {d.money.length + d.sends.length > 0 && (
              <Section title="Money" phone={phone}>
                {d.money.map((r) => <Money key={r.ask.id} row={r} phone={phone} main={main === `ask-${r.ask.id}`} me={me.name} />)}
                {d.sends.map((s) => <HeldSend key={s.job_id} send={s} phone={phone} main={main === `job-${s.job_id}`} mark={job === s.job_id} />)}
              </Section>
            )}
            {d.stuck.length > 0 && <Section title="Stuck" phone={phone}>{d.stuck.map((s) => <StuckRow key={s.video.id} row={s} phone={phone} />)}</Section>}
          </>
        )}
      </main>
    </div>
  );
}
