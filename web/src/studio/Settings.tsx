import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { studioName } from "../auth/pages";
import { useMe } from "../auth/useMe";
import { useRestoreBrand } from "../brand/ArchiveBrand";
import { useLanguages } from "../languages/useLanguages";
import { lookMedia } from "../newvideo/Cards";
import { useLooks } from "../scripts/Looks";
import { useWorkspace } from "../settings/StudioName";
import { useToast } from "../toast";
import { Money } from "../usage/parts";
import { useBrandRows, type BrandRow } from "../usage/useUsage";
import { Dialog } from "./Dialog";
import { setNewLook } from "./look";
import "./settings.css";

/** Something that is on or off for the whole studio: a look, a language. `fixed`: always on, so it has no switch. */
type Switch = { id: string; name: string; note: string; on: boolean; fixed: boolean; picture?: string };

/** Settings in the new look (the redesign, stage 6), for the owner: the studio's name, its brands (set up, archive with
 *  Undo, bring back, new), which looks and languages are on, and the way back to the current site. Each change is the
 *  request the current Settings sends. Samples and tests (which cost money), credit limits and the team stay on the
 *  current site, one link away. */
export function Settings() {
  const me = useMe().data;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const looks = useLooks();
  const languages = useLanguages();
  const fresh = (key: string) => queryClient.invalidateQueries({ queryKey: [key] });
  if (!me) return null;
  return (
    <>
      <header className="head">
        <h1>Settings</h1>
      </header>
      <div className="view">
        {me.role !== "owner" ? (
          <p className="none">Only the owner manages settings.</p>
        ) : (
          <div className="page setpage">
            <Studio owner={me.name} />
            <Brands />
            <Switches
              title="Looks"
              why="Looks that are on show up on New video. Each one comes with its own way of shooting."
              failed={looks.isError}
              items={(looks.data ?? []).map((l) => ({ id: l.id, name: l.name, note: l.card || l.blurb, on: l.on, fixed: l.id === "house", picture: lookMedia(l).still }))}
              set={async (id, on) => {
                await must(api.PATCH("/looks/{look_id}", { params: { path: { look_id: id } }, body: { on } }));
                await fresh("looks");
              }}
              said={(s, on) => (on ? `${s.name} is on.` : `${s.name} is off. Videos using it keep it.`)}
            />
            <Switches
              title="Languages"
              why="The languages a script can be written in."
              failed={languages.isError}
              items={(languages.data ?? []).map((l) => ({ id: l.id, name: l.name, note: "", on: l.on, fixed: l.id === "en" }))}
              set={async (id, on) => {
                await must(api.PATCH("/languages/{language}", { params: { path: { language: id } }, body: { on } }));
                await fresh("languages");
              }}
              said={(s, on) => (on ? `${s.name} is on.` : `${s.name} is off. Scripts in it keep it; new scripts start in English.`)}
            />
            <section aria-labelledby="set-look">
              <h2 id="set-look">Try the new look</h2>
              <div className="rowl">
                <span className="tx2">
                  <b>You are using the new look</b>
                  <small>Only on this computer. The current site is still there, and you can come back any time.</small>
                </span>
                <button
                  type="button"
                  className="btn soft"
                  onClick={() => {
                    setNewLook(false);
                    navigate("/");
                  }}
                >
                  Use the current site
                </button>
              </div>
            </section>
            <p className="quiet why">
              Still on the current site: <Link to="/settings?tab=limits">credit limits</Link>, <Link to="/team">the team</Link>, and making <Link to="/settings?tab=looks">a look’s sample</Link> or <Link to="/settings?tab=languages">a language’s test script</Link>.
            </p>
          </div>
        )}
      </div>
    </>
  );
}

/** The studio's name, shown at the top of the rail and on invite links. It saves when the field is left (or on Enter),
 *  and only if it was changed to something. */
function Studio({ owner }: { owner: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const saved = useWorkspace().data;
  const [edit, setEdit] = useState<string | null>(null);
  const put = async (name: string) => {
    const { data, error } = await api.PUT("/workspace", { body: { name } });
    if (!data) return toast(errorText(error), undefined, "error");
    queryClient.setQueryData(["workspace"], data);
    return data;
  };
  const leave = async () => {
    const name = edit?.trim();
    if (!saved || edit === null) return;
    if (!name || name === saved.name) return setEdit(null); // nothing to save: the saved name shows again
    const before = saved.name;
    if (!(await put(name))) return;
    setEdit(null);
    toast("Studio name saved.", () => void put(before));
  };
  return (
    <section aria-labelledby="set-studio">
      <h2 id="set-studio">Studio</h2>
      <label className="rowl">
        <span className="tx2">
          <b>Name</b>
          <small>Shown at the top left, and on invite links.</small>
        </span>
        <input className="field" aria-label="Studio name" maxLength={120} disabled={!saved} value={edit ?? (saved ? studioName(saved.name, owner) : "")} onChange={(e) => setEdit(e.target.value)} onBlur={() => void leave()} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
      </label>
    </section>
  );
}

/** Every brand with what the server says it has made and spent so far: set one up, archive one (it asks first, and the
 *  toast has Undo), bring an archived one back, or start a new one. The only brand left can't be archived here. */
function Brands() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const restore = useRestoreBrand();
  const rows = useBrandRows({ period: "all", q: "", archived: true, sort: "name" });
  const brands = rows.data?.pages.flatMap((p) => p.items) ?? [];
  const live = brands.filter((b) => !b.archived);
  const [asking, setAsking] = useState<BrandRow | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const archive = async (b: BrandRow) => {
    setBusy(true);
    setProblem(null);
    const { error, response } = await api.DELETE("/brands/{brand_id}", { params: { path: { brand_id: b.brand_id } } });
    setBusy(false);
    if (!response.ok) return setProblem(errorText(error));
    setAsking(null);
    await Promise.all([queryClient.invalidateQueries({ queryKey: ["brands"] }), queryClient.invalidateQueries({ queryKey: ["usage"] })]);
    toast(`Archived ${b.name}.`, () => void restore({ id: b.brand_id, name: b.name }));
  };
  const row = (b: BrandRow) => (
    <li key={b.brand_id} className="rowl">
      <i aria-hidden className="sq" style={{ background: b.colour || "var(--accent)" }} />
      <span className="tx2">
        <b>{b.name}</b>
        <small>
          {b.archived && "Archived · "}
          {b.videos} video{b.videos === 1 ? "" : "s"} · <Money value={b.spend_usd} estimated={b.spend_estimated} /> spent so far
        </small>
      </span>
      {b.archived ? (
        <button type="button" className="btn ghost" aria-label={`Bring back ${b.name}`} onClick={() => void restore({ id: b.brand_id, name: b.name })}>
          Bring back
        </button>
      ) : (
        <>
          <Link className="btn ghost" aria-label={`Set up ${b.name}`} to={`/s/b/${b.brand_id}/setup`}>
            Set up
          </Link>
          {live.length > 1 && (
            <button type="button" className="btn ghost" aria-label={`Archive ${b.name}`} onClick={() => (setProblem(null), setAsking(b))}>
              Archive
            </button>
          )}
        </>
      )}
    </li>
  );
  return (
    <section aria-labelledby="set-brands">
      <h2 id="set-brands">
        Brands
        <Link className="btn soft" to="/s/brands/new">
          <Plus size={14} strokeWidth={1.75} aria-hidden />
          New brand
        </Link>
      </h2>
      {rows.isError && (
        <p role="alert" className="none">
          Could not load the brands.
        </p>
      )}
      <ul>
        {live.map(row)}
        {brands.filter((b) => b.archived).map(row)}
      </ul>
      {rows.hasNextPage && (
        <button type="button" className="btn soft" onClick={() => void rows.fetchNextPage()}>
          Show more brands
        </button>
      )}
      {asking && (
        <Dialog title={`Archive ${asking.name}?`} confirm="Archive" busy={busy} onConfirm={() => void archive(asking)} onClose={() => setAsking(null)}>
          <p className="dsub">It leaves the brand menu. Its videos, people and clips are kept, and you can bring it back from here.</p>
          {problem && (
            <p role="alert" className="dsub bad">
              Couldn’t do that. Nothing changed. {problem}
            </p>
          )}
        </Dialog>
      )}
    </section>
  );
}

/** A list of switches. A press sends the change, says what happened with Undo, and shows the server's own words when
 *  it refuses (a look needs its sample first, a language its test). One at a time. */
function Switches({ title, why, failed, items, set, said }: { title: string; why: string; failed: boolean; items: Switch[]; set: (id: string, on: boolean) => Promise<void>; said: (s: Switch, on: boolean) => string }) {
  const toast = useToast();
  const busy = useRef(false);
  const turn = async (s: Switch, on: boolean, undo = true) => {
    if (busy.current) return;
    busy.current = true;
    try {
      await set(s.id, on);
      toast(said(s, on), undo ? () => void turn(s, !on, false) : undefined);
    } catch (e) {
      toast((e as Error).message, undefined, "error", true);
    }
    busy.current = false;
  };
  const inner = (s: Switch) => (
    <>
      {s.picture && <img src={s.picture} alt="" loading="lazy" />}
      <span className="tx2">
        <b>{s.name}</b>
        {s.note && <small>{s.note}</small>}
      </span>
    </>
  );
  return (
    <section aria-labelledby={`set-${title}`}>
      <h2 id={`set-${title}`}>{title}</h2>
      <p className="why">{why}</p>
      {failed && (
        <p role="alert" className="none">
          Could not load the {title.toLowerCase()}.
        </p>
      )}
      <ul className="lks">
        {items.map((s) => (
          <li key={s.id}>
            {s.fixed ? (
              <div className="rowl">
                {inner(s)}
                <span className="fix">Always on</span>
              </div>
            ) : (
              <button type="button" role="switch" aria-checked={s.on} aria-label={s.name} className="rowl" onClick={() => void turn(s, !s.on)}>
                {inner(s)}
                <i aria-hidden className="sw" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
