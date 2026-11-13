import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Pencil, Plus, RefreshCw, Trash2, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useJobs } from "../clip/History";
import { textSize } from "../components";
import { itemWords, useApproveSheet, useArchive, useCreateItem, useDrawSheet, useItem, usePickVoice, useSaveItem } from "../library/itemActions";
import { STATUS, USED } from "../library/ItemPage";
import { cover, day, upTo, useItems, useNewPrice, type Item } from "../library/kinds";
import { SHEET_NOTE, lookFitNote } from "../library/sheets";
import { sampleOf, useVoiceList, voiceOf } from "../library/Voices";
import { useBrands } from "../shell/useBrands";
import { Dialog } from "./Dialog";
import { Failed, FileRow, Head, Hold, ICON, Loading, PlayButton, usePick } from "./libraryParts";
import { Choice, Popover } from "./Popover";
import { plural } from "./script";
import { useLock } from "./useLock";

const DOT: Record<string, string> = { approved: "ok", needs_approval: "wait", none: "idle" };
const BUSY = ["drawing", "waiting_for_owner"];

/** Library › Cast: the brand's saved people as tiles, a face and a name each (the tile a video's Cast view uses). The
 *  picked one's panel has their sheet whole, who they are, their voice, the videos they are in, and their presses. */
export function CastTab({ brandId }: { brandId: number }) {
  const people = useItems("character", brandId);
  const places = useItems("place", brandId).data?.length ?? 0;
  const brand = useBrands().data?.find((b) => b.id === brandId)?.name ?? "this brand";
  const [picked, pick] = usePick();
  const [adding, setAdding] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const list = people.data ?? [];
  const person = list.find((p) => p.id === picked) ?? list[0];
  const add = (
    <button type="button" className="btn go" onClick={() => setAdding(true)}>
      <Plus {...ICON} />
      New person
    </button>
  );
  return (
    <>
      <Head action={list.length > 0 && add} />
      <div className="view">
        <div className="page lib">
          {people.isPending ? (
            <Loading />
          ) : people.isError ? (
            <Failed icon={Users} what="the cast" error={people.error} again={() => void people.refetch()} />
          ) : !person ? (
            <Hold icon={Users} title={`Nobody saved in ${brand} yet`} action={add}>
              Save a person and give them a role when you paste a script. Every clip keeps their face.
            </Hold>
          ) : (
            <div className="shelf">
              <div className="tiles big" role="group" aria-label="Saved people">
                {list.map((p) => (
                  <button key={p.id} type="button" className="tile person" aria-pressed={p === person} onClick={() => (pick(p.id), panel.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" }))}>
                    <span className="im">{cover(p) != null ? <img src={fileUrl(cover(p)!)} alt="" loading="lazy" /> : <small aria-hidden>{STATUS[p.sheet_status]?.words}</small>}</span>
                    <b>{p.name}</b>
                  </button>
                ))}
              </div>
              <div ref={panel} className="pcard" role="region" aria-label={person.name}>
                <Person key={person.id} brandId={brandId} brand={brand} listed={person} />
              </div>
            </div>
          )}
          {person && (
            <p className="hint also">
              People you removed can be brought back on <Link to={`/b/${brandId}/library/characters`}>the current site</Link>, under Show archived.
            </p>
          )}
          {places > 0 && (
            <p className="hint also">
              {brand} also has {plural(places, "saved place")}. Places are on <Link to={`/b/${brandId}/library/places`}>the current site</Link>.
            </p>
          )}
        </div>
      </div>
      {adding && <NewPerson brandId={brandId} onMade={pick} onClose={() => setAdding(false)} />}
    </>
  );
}

/** One saved person: the sheet whole, who they are, their voice and videos, and the current site's own presses for
 *  them. Read again every 3 s while the sheet is drawn; the grid is read again when the sheet's state changes. */
function Person({ brandId, brand, listed }: { brandId: number; brand: string; listed: Item }) {
  const read = useItem("character", listed.id);
  const item = read.data ?? listed;
  const queryClient = useQueryClient();
  useEffect(() => {
    if (item.sheet_status !== listed.sheet_status) void queryClient.invalidateQueries({ queryKey: ["library", "character", brandId] });
  }, [item.sheet_status]); // eslint-disable-line react-hooks/exhaustive-deps
  const [asking, setAsking] = useState<"edit" | "look" | "remove" | null>(null);
  const [note, setNote] = useState("");
  const draw = useDrawSheet("character", item.id, () => setAsking(null));
  const approve = useApproveSheet("character", item);
  const archive = useArchive("character", item, () => setAsking(null));
  const lock = useLock(draw.isPending); // a sheet is paid: one request a press, however fast it is pressed (./useLock)
  const jobs = useJobs();
  const busy = BUSY.includes(item.sheet_status);
  const last = (jobs.data ?? []).filter((j) => j.step === "sheet" && j.library_item_id === item.id).sort((a, b) => b.id - a.id)[0];
  const picture = cover(item);
  const drawCost = upTo(item.sheet_credits || undefined, item.usd?.sheet);
  const changeCost = upTo(item.change_credits || undefined, item.usd?.change);
  const size = textSize(note, SHEET_NOTE);
  const used = item.used_in ?? [];
  const refused = draw.error ?? approve.error ?? archive.error;
  const change = (about: string) => (draw.reset(), setNote(about), setAsking("look"));
  return (
    <>
      <div className="psheet">{picture != null ? <img src={fileUrl(picture)} alt={`${item.name}’s sheet`} /> : <span>{STATUS[item.sheet_status]?.words}</span>}</div>
      <div className="pname">
        <h2>{item.name}</h2>
        <span className="st" role="status">
          <i aria-hidden className={`dot ${DOT[item.sheet_status] ?? ""}`} />
          {STATUS[item.sheet_status]?.words}
        </span>
      </div>
      <p className="line">{item.notes || "No description yet."}</p>
      {item.look_fit && !busy && (
        <p className="advice" role="note">
          {lookFitNote(item.look_fit)}{" "}
          <button type="button" onClick={() => change(item.look_fit!.problem)}>
            Fix it with a note
          </button>
        </p>
      )}
      {last?.status === "failed" && !busy && (
        <p className="hint bad" role="alert">
          The sheet didn’t finish. Nothing was charged.
        </p>
      )}
      <dl className="facts">
        <dt>Voice</dt>
        <dd>
          <VoiceOf brandId={brandId} item={item} />
        </dd>
        <dt>Videos</dt>
        <dd>
          {used.length === 0
            ? "Not in a video yet."
            : used.map((u) => (
                <Link key={u.project_id} to={`/s/b/${brandId}/videos/${u.project_id}`}>
                  <span className="clip">{u.name}</span>
                  <small>{[USED[u.status][0], u.at && day(u.at)].filter(Boolean).join(" · ")}</small>
                </Link>
              ))}
        </dd>
      </dl>
      <div className="offers">
        {item.sheet_status === "needs_approval" && (
          <button type="button" className="btn soft" disabled={approve.isPending} onClick={() => approve.mutate()}>
            <Check {...ICON} size={14} />
            Approve
          </button>
        )}
        {item.sheet_status === "none" ? (
          <button type="button" className="btn soft" disabled={draw.isPending} onClick={() => lock((done) => draw.mutate("", { onSettled: done }))}>
            <RefreshCw {...ICON} size={14} />
            {last?.status === "failed" ? "Draw again" : "Draw the sheet"} {drawCost && <small>{drawCost}</small>}
          </button>
        ) : (
          !busy && (
            <button type="button" className="btn soft" onClick={() => change("")}>
              <Pencil {...ICON} size={14} />
              Change look… {changeCost && <small>{changeCost}</small>}
            </button>
          )
        )}
        <button type="button" className="btn soft" onClick={() => setAsking("edit")}>
          Rename or describe…
        </button>
        <button type="button" className="btn ghost" onClick={() => (archive.reset(), setAsking("remove"))}>
          <Trash2 {...ICON} size={14} />
          Remove
        </button>
      </div>
      {refused && asking === null && (
        <p className="hint bad" role="alert">
          {refused.message}
        </p>
      )}
      <p className="hint also">
        Their sheets in other looks, outfits, usual place and history are on <Link to={`/b/${brandId}/library/characters/${item.id}`}>the current site</Link>.
      </p>
      {asking === "look" && (
        <Dialog title={`Change ${item.name}’s look`} confirm={changeCost ? `Change it · ${changeCost}` : "Change it"} busy={!note.trim() || size.over || draw.isPending} onClose={() => setAsking(null)} onConfirm={() => lock((done) => draw.mutate(note.trim(), { onSettled: done }))}>
          <input data-autofocus aria-label="What should change?" placeholder="What should change? “Navy polo, no hat, a little older”" value={note} onChange={(e) => (setNote(e.target.value), draw.reset())} />
          <p className={`hint${size.over ? " bad" : ""}`}>{size.error ?? "Their sheet is drawn again with this change, then waits for your OK."}</p>
          {draw.isError && (
            <p className="dsub bad" role="alert">
              {draw.error.message}
            </p>
          )}
        </Dialog>
      )}
      {asking === "edit" && <Edit item={item} onClose={() => setAsking(null)} />}
      {asking === "remove" && (
        <Dialog title={`Remove ${item.name}?`} confirm="Remove" busy={archive.isPending} onClose={() => setAsking(null)} onConfirm={() => archive.mutate()}>
          <p className="dsub">
            {item.name} leaves {brand}’s cast. Videos already made keep them, and Undo brings them back.
          </p>
          {archive.isError && (
            <p className="dsub bad" role="alert">
              {archive.error.message}
            </p>
          )}
        </Dialog>
      )}
    </>
  );
}

/** A person's voice: its name and sample, and another picked from the brand's voices and the app's (free). */
function VoiceOf({ brandId, item }: { brandId: number; item: Item }) {
  const voices = useVoiceList(brandId).data?.voices ?? [];
  const pick = usePickVoice(item.id);
  const voice = voiceOf(item, voices);
  const sample = voice ? sampleOf(voice) : item.voice_file_id ? fileUrl(item.voice_file_id) : null;
  const words = voice ? [voice.name, voice.description.split(",")[0].toLowerCase()].filter(Boolean).join(" · ") : item.voice_file_id ? "Their own voice sample" : "None yet";
  return (
    <span className="voice">
      {sample && <PlayButton src={sample} of={`${item.name}’s voice`} />}
      <span className="clip">{words}</span>
      <Popover
        label={`${item.name}’s voice`}
        end
        button={(p) => (
          <button type="button" className="btn ghost" disabled={pick.isPending} {...p}>
            {voice ? "Change" : "Pick a voice"}
            <ChevronDown {...ICON} size={14} />
          </button>
        )}
      >
        {(close) => (
          <>
            {voices
              .filter((v) => v.state !== "expired" && v.state !== "failed")
              .map((v) => (
                <Choice key={v.id ?? v.stock_key ?? v.name} checked={v === voice} note={v.description} onPick={() => (close(), pick.mutate(v))}>
                  {v.name}
                </Choice>
              ))}
            {voice && (
              <Choice checked={false} onPick={() => (close(), pick.mutate(null))}>
                No voice
              </Choice>
            )}
          </>
        )}
      </Popover>
      {pick.isError && (
        <small className="bad" role="alert">
          {pick.error.message}
        </small>
      )}
    </span>
  );
}

/** Rename a person or say who they are (free): the current site's own save, every other word as it is. */
function Edit({ item, onClose }: { item: Item; onClose: () => void }) {
  const [name, setName] = useState(item.name);
  const [notes, setNotes] = useState(item.notes);
  const save = useSaveItem("character", item.id);
  const same = name === item.name && notes === item.notes;
  return (
    <Dialog title={`Rename or describe ${item.name}`} confirm="Save" busy={same || !name.trim() || save.isPending} onClose={onClose} onConfirm={() => save.mutate({ ...itemWords(item), name, notes }, { onSuccess: onClose })}>
      <label className="dlab">
        Name
        <input data-autofocus value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="dlab">
        Who they are
        <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <p className="hint">After a change here their sheet asks for your OK again.</p>
      {save.isError && (
        <p className="dsub bad" role="alert">
          {save.error.message}
        </p>
      )}
    </Dialog>
  );
}

/** New person: a name and a line, or a photo; then their sheet is drawn (paid, the server's price on the press, one
 *  request a press). Exactly what the current site's New character sends. */
function NewPerson({ brandId, onMade, onClose }: { brandId: number; onMade: (id: number) => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [words, setWords] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const price = useNewPrice("character").data;
  const cost = upTo(price?.credits, price?.usd);
  const { create, locked } = useCreateItem(brandId, "character", (id) => (onMade(id), onClose()));
  const lock = useLock(create.isPending);
  const ready = !!name.trim() && (!!photo || !!words.trim());
  return (
    <Dialog title="New person" confirm={cost ? `Draw their sheet · ${cost}` : "Draw their sheet"} busy={!ready || create.isPending} onClose={onClose} onConfirm={() => lock((done) => create.mutate({ name, words, photo, more: [], type: "physical" }, { onSettled: done }))}>
      <label className="dlab">
        Name
        <input data-autofocus value={name} maxLength={120} disabled={locked} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="dlab">
        Who they are, in a line
        <input value={words} disabled={locked} placeholder="A mom in her forties, tired, warm" onChange={(e) => setWords(e.target.value)} />
      </label>
      <FileRow label="Or upload a photo" note="Their sheet is drawn from it. The photo itself is never used in a video." accept="image/*" file={photo?.name ?? ""} disabled={locked} onPick={([f]) => setPhoto(f)} />
      <p className="hint">Their sheet is drawn, then waits for your OK.</p>
      {create.isError && (
        <p className="dsub bad" role="alert">
          {create.error.message}
        </p>
      )}
    </Dialog>
  );
}
