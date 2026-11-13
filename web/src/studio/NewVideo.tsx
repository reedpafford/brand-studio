import { Fragment, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Folder, LoaderCircle, Paperclip, Plus, Upload, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useFolders } from "../folders/Projects";
import { SHAPES, sentTo, type Shape } from "../freestyle/useFreestyle";
import { useMode, useSaved } from "../home/useDraft";
import { cover, type Item } from "../library/kinds";
import { ACCEPT, useAttachments } from "../newvideo/Attach";
import { lookMedia, type Look } from "../newvideo/Cards";
import { pressWords } from "../newvideo/Press";
import { useEstimate, useSend, type Send } from "../newvideo/useNewVideo";
import { notMadeAs, useLooks } from "../scripts/Looks";
import { scriptSize } from "../scripts/ScriptFrame";
import { useFormats, type Format } from "../scripts/useFormats";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { Choice, Popover, type ButtonProps } from "./Popover";
import { ScriptBox } from "./ScriptBox";
import { hookCount, readOut, roleName, roles as rolesIn } from "./script";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
const SMALL = { ...ICON, size: 14 } as const;
const MOST_FILES = 6;
const SHAPE: Record<Shape, { name: string; where: string }> = { "9:16": { name: "Tall", where: "Reels, TikTok, Shorts" }, "1:1": { name: "Square", where: "Feed" }, "16:9": { name: "Wide", where: "YouTube" } };
const READS = "new-video-reads";

type Picked = { type?: string; look?: string; shape?: Shape; folder?: number | null; product?: number | null; cast?: Record<string, number | null>; hooks?: "all" | "first" };

/** A format that can be picked on this site: on in its guide, and not waiting on something ("coming next"). */
const usable = (f: Format) => f.on && !f.off;
const shape = (s: Shape) => <i aria-hidden className={`shp s${s.replace(":", "")}`} />;
const picture = (i: Item, className?: string) => {
  const id = cover(i);
  return id ? <img key={i.id} src={fileUrl(id)} alt="" className={className} /> : null;
};
/** A setting as a pill that opens its menu: its name dim (`bare`: left out), then what is picked; a screen reader
 *  hears both ("Product: The director decides"). */
const pill = (name: string, value: string, { lead, trail, bare }: { lead?: ReactNode; trail?: ReactNode; bare?: boolean } = {}) => (p: ButtonProps) => (
  <button type="button" className="pill" aria-label={`${name}: ${value}`} {...p}>
    {lead}
    {!bare && <em>{name}</em>}
    <span className="clip">{value}</span>
    {trail}
  </button>
);

/** The large preview: the look's sample, playing, with its name and line; `preview` marks one that isn't the chosen look. */
function Monitor({ look, preview }: { look?: Look; preview: boolean }) {
  const media = look && lookMedia(look);
  return (
    <div className={preview ? "monitor peek" : "monitor"}>
      {look && media && (
        <>
          {media.clip ? <video key={media.clip} src={media.clip} poster={media.still} muted loop playsInline autoPlay aria-label={`${look.name} sample`} /> : media.still && <img src={media.still} alt="" />}
          <span>
            <b>{look.name}</b>
            <small>{look.card || look.blurb}</small>
          </span>
        </>
      )}
    </div>
  );
}

/** New video in the new look (the redesign, stage 1): the script on the left, in a box that reads the paste; the look,
 *  the price and Make it on the right. It posts the same send as the current screen, with the cast as roles
 *  (`cast: [{role, item_id}]`, nobody saved unless given a role), the script always word for word (`idea: false`), and
 *  no product unless one is picked. A script with two or more openings also says which to film (`hooks`): all of
 *  them, as versions of one video over one body, unless he picks the first only. The video then opens on its page
 *  here (Video.tsx). */
export function NewVideo() {
  const brandId = Number(useParams().brandId);
  const owner = useMe().data?.role === "owner";
  const brands = useBrands().data;
  const brand = brands?.find((b) => b.id === brandId);
  const navigate = useNavigate();
  const toast = useToast();
  const formats = useFormats().data ?? [];
  const lookList = useLooks();
  const looks = (lookList.data ?? []).filter((l) => l.on);
  const folders = useFolders(brandId).data ?? [];
  const people = useSaved("character", brandId).data ?? [];
  const products = useSaved("prop", brandId).data ?? [];
  const files = useAttachments();
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useMode(owner);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Picked>({});
  const pick = (p: Picked) => setPicked((was) => ({ ...was, ...p }));
  const [peek, setPeek] = useState<string | null>(null); // the look under the pointer
  const [roleOpen, setRoleOpen] = useState("");

  // Every pick is read against what the brand has now, so nothing from another brand or a line since deleted is sent.
  const format = formats.find((f) => f.id === picked.type) ?? formats.find(usable);
  const look = looks.find((l) => l.id === picked.look) ?? looks.find((l) => !notMadeAs(l, format?.id, formats));
  const folder = folders.find((f) => f.id === picked.folder);
  const product = products.find((p) => p.id === picked.product);
  const roles = rolesIn(text);
  const cast = roles.flatMap((role) => {
    const who = people.find((p) => p.id === picked.cast?.[role]);
    return who ? [{ role, who }] : [];
  });
  const size = scriptSize(text);
  const openings = hookCount(text);
  const hooks = openings > 1 ? (picked.hooks ?? "all") : null; // an ordinary script says nothing about hooks
  const send: Send = { type: format?.id ?? "", look: look?.id ?? "", shape: picked.shape ?? "9:16", brand_id: brandId, text: text.trim(), folder_id: folder?.id ?? null, cast: cast.map((c) => ({ role: c.role, item_id: c.who.id })), attachments: files.ids, mode, product_ids: product ? [product.id] : [], idea: false, ...(hooks && { hooks }) };
  const priced = !!send.text && !size.over && !!look && !!format;
  const ready = priced && !files.busy;
  const price = useEstimate(priced ? send : null, true);
  // Its video opens here in the new look; a send with no video to open yet (held for the owner) opens where it always did.
  const sent = useSend((fs) => navigate(sentTo(fs, owner, brandId).replace(/^(?=\/b\/\d+\/videos\/)/, "/s")));
  const starting = sent.isPending || sent.isSuccess; // off from the press until the video opens
  const pressed = useRef(false); // one press only: a second tap can land before the screen has heard of the first
  const go = () => {
    if (!ready || pressed.current) return;
    pressed.current = true;
    sent.mutate(send, { onError: () => (pressed.current = false) });
  };
  if (brands && !brand) return <p className="none">That brand doesn’t exist.</p>;

  /** A look not made in the format on screen moves the format to the first it is made in, and says so. */
  const pickLook = (l: Look) => {
    const why = notMadeAs(l, format?.id, formats);
    const to = why ? formats.find((f) => l.formats.includes(f.id) && usable(f)) : undefined;
    if (why && !to) return (setPeek(null), toast(why, undefined, "error", true));
    pick({ look: l.id, ...(to && { type: to.id }) });
    if (to) toast(`${why} The format is ${to.name} now.`);
  };
  const attach = (list: FileList | null) => {
    const chosen = Array.from(list ?? []);
    const room = MOST_FILES - files.files.length;
    files.add(chosen.slice(0, room));
    if (chosen.length > room) toast("That’s six, the most a video takes.");
  };
  /** Gives a role to someone saved (or back to New), closes its list and puts focus back on the role. */
  const give = (role: string, id: number | null) => {
    (document.activeElement?.closest(".sub")?.previousElementSibling as HTMLElement | null)?.focus();
    pick({ cast: { ...picked.cast, [role]: id } });
    setRoleOpen("");
  };

  const shown = looks.find((l) => l.id === peek) ?? look;
  const more = owner && looks.length % 2 === 1; // an odd grid's last cell: the way to the looks that are off
  const words = pressWords(owner, price);
  const about = !send.text ? "No script yet" : !priced ? "No price yet" : words.most ? `${words.most.charAt(0).toUpperCase()}${words.most.slice(1)}` : "Working out the price…";
  // The price is always for the whole script, every opening: with the first only, that is said, never a made-up figure.
  const under = price.failed ?? (words.held ? "The owner approves before anything is made." : hooks === "first" && price.est ? "This is for every hook. With the first only it will be less; the plan gives the real price." : `${price.est && !price.est.expected ? "The most it can charge." : "An estimate."} What it really spends shows on the video as it goes.`);
  const productName = product?.name ?? (products.length ? "The director decides" : "None yet");
  const castName = cast[0] ? `${cast[0].who.name} as ${roleName(cast[0].role)}${cast.length > 1 ? ` +${cast.length - 1}` : ""}` : "New for this video";

  return (
    <>
      <header className="head">
        <h1>New video</h1>
        <span className="grow" />
        <Popover end label="Save in" button={pill("Save in", folder?.name ?? "Unsorted", { lead: <Folder {...SMALL} /> })}>
          {(close) => (
            <>
              <h6>Save in</h6>
              <Choice checked={!folder} onPick={() => (pick({ folder: null }), close())}>
                Unsorted
              </Choice>
              {folders.map((f) => (
                <Choice key={f.id} checked={f.id === folder?.id} onPick={() => (pick({ folder: f.id }), close())}>
                  {f.name}
                </Choice>
              ))}
            </>
          )}
        </Popover>
      </header>
      <div className="view">
        <div className="create">
          <div className="desk">
            <section className="write" aria-labelledby="new-video-script">
              <h2 id="new-video-script">Script</h2>
              <ScriptBox text={text} setText={setText} go={go} describedBy={READS}>
                <p id={READS} className="reads" role={size.error ? "alert" : undefined}>
                  {size.error ?? readOut(text)}
                </p>
                {files.files.length > 0 && (
                  <ul className="files" aria-label="For this video only">
                    {files.files.map((f) => (
                      <li key={f.local} className="chipf">
                        {!f.id && !f.error ? <LoaderCircle {...SMALL} className="spin" /> : f.video ? <video src={f.local} muted preload="metadata" /> : <img src={f.local} alt="" />}
                        <span>
                          <b>{f.name}</b>
                          <small className={f.error ? "bad" : undefined}>{f.error ?? (f.id ? "For this video only" : "Uploading…")}</small>
                        </span>
                        <button type="button" className="x" aria-label={`Remove ${f.name}`} onClick={() => files.remove(f.local)}>
                          <X {...SMALL} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="bar">
                  <input ref={input} type="file" hidden multiple accept={ACCEPT} aria-label="Upload pictures or clips" onChange={(e) => (attach(e.target.files), (e.target.value = ""))} />
                  <Popover
                    label="Add to this video"
                    button={(p) => (
                      <button type="button" className="btn ghost square" aria-label="Add to this video" title="Add to this video" {...p}>
                        <Paperclip {...ICON} />
                      </button>
                    )}
                  >
                    {(close) => (
                      <button type="button" role="menuitem" onClick={() => (close(), files.files.length < MOST_FILES ? input.current?.click() : toast("That’s six, the most a video takes."))}>
                        <Upload {...ICON} />
                        <span className="ol">
                          <b>Upload pictures or clips</b>
                          <small>Used for this video only. Up to {MOST_FILES}.</small>
                        </span>
                      </button>
                    )}
                  </Popover>
                  <Popover label="Product" button={pill("Product", productName, { lead: product && picture(product) })}>
                    {(close) => (
                      <>
                        <h6>Product in this video</h6>
                        <Choice checked={!product} note="Shown where the script calls for it" onPick={() => (pick({ product: null }), close())}>
                          The director decides
                        </Choice>
                        {products.map((p) => (
                          <Choice key={p.id} checked={p.id === product?.id} lead={picture(p, "pth")} note="Always shown, exactly as the real thing" onPick={() => (pick({ product: p.id }), close())}>
                            {p.name}
                          </Choice>
                        ))}
                        {products.length === 0 && <p className="pe">{brand?.name ?? "This brand"} has no product saved yet.</p>}
                        <a className="pa" href={`/b/${brandId}/library/products?new=1`} target="_blank" rel="noreferrer">
                          <Plus {...ICON} />
                          Add a product
                        </a>
                      </>
                    )}
                  </Popover>
                  <Popover label="Cast" button={pill("Cast", castName, { lead: cast.length > 0 && <span className="faces">{cast.slice(0, 3).map((c) => picture(c.who))}</span> })}>
                    {() =>
                      people.length === 0 ? (
                        <p className="pe">Nobody is saved in {brand?.name ?? "this brand"} yet. The director draws everyone for this video.</p>
                      ) : (
                        <>
                          <h6>Who plays who</h6>
                          {roles.length === 0 && <p className="pe">No named speakers in this script. The director draws whoever it needs.</p>}
                          {roles.map((role) => {
                            const who = cast.find((c) => c.role === role)?.who;
                            const open = roleOpen === role;
                            return (
                              <Fragment key={role}>
                                <button type="button" aria-label={`${roleName(role)}: ${who?.name ?? "New"}`} aria-expanded={open} onClick={() => setRoleOpen(open ? "" : role)}>
                                  <span className="ol">
                                    <b>{roleName(role)}</b>
                                  </span>
                                  <span className={who ? "rv set" : "rv"}>{who?.name ?? "New"}</span>
                                  <ChevronRight {...SMALL} className="chev" />
                                </button>
                                {open && (
                                  <div className="sub" role="group" aria-label={`Who plays ${roleName(role)}`}>
                                    <Choice checked={!who} onPick={() => give(role, null)}>
                                      New for this video
                                    </Choice>
                                    {people.map((p) => (
                                      <Choice key={p.id} checked={p.id === who?.id} note={p.short_description ?? undefined} onPick={() => give(role, p.id)}>
                                        {p.name}
                                      </Choice>
                                    ))}
                                  </div>
                                )}
                              </Fragment>
                            );
                          })}
                          <p className="pe">Anyone left as New is drawn for this video. Nobody saved is used unless you give them a role here.</p>
                        </>
                      )
                    }
                  </Popover>
                  {hooks && (
                    <Popover label="Hooks" button={pill("Hooks", hooks === "all" ? `All ${openings}` : "First only")}>
                      {(close) => (
                        <>
                          <h6>Which hooks to film</h6>
                          <Choice checked={hooks === "all"} note={`One video with ${openings} versions: each hook over the same body`} onPick={() => (pick({ hooks: "all" }), close())}>
                            All {openings} hooks
                          </Choice>
                          <Choice checked={hooks === "first"} note="The other hooks are left out of this video" onPick={() => (pick({ hooks: "first" }), close())}>
                            First only
                          </Choice>
                        </>
                      )}
                    </Popover>
                  )}
                  <Popover label="Shape" button={pill("Shape", send.shape, { lead: shape(send.shape), bare: true })}>
                    {(close) =>
                      SHAPES.map((s) => (
                        <Choice key={s} checked={s === send.shape} lead={shape(s)} note={SHAPE[s].where} onPick={() => (pick({ shape: s }), close())}>
                          {SHAPE[s].name} · {s}
                        </Choice>
                      ))
                    }
                  </Popover>
                </div>
              </ScriptBox>
            </section>
            <aside className="side" aria-label="Look and price">
              <div className="h2row">
                <h2>Look</h2>
                <Popover end label="Format" button={pill("Format", format?.name ?? "None", { trail: <ChevronDown {...SMALL} /> })}>
                  {(close) => (
                    <>
                      <h6>How the words are delivered</h6>
                      {formats.map((f) => {
                        const off = !usable(f) ? (f.off && f.off !== "off" ? `Coming next: ${f.off}` : "Off on this site") : look && notMadeAs(look, f.id, formats) ? `Not made in ${look.name}` : "";
                        return (
                          <Choice key={f.id} checked={f.id === format?.id} disabled={!!off} note={off || f.card || f.blurb} onPick={() => (pick({ type: f.id, look: look?.id }), close())}>
                            {f.name}
                          </Choice>
                        );
                      })}
                    </>
                  )}
                </Popover>
              </div>
              {lookList.isSuccess && looks.length === 0 ? (
                <p className="none">No look is switched on. The owner turns looks on in Settings.</p>
              ) : (
                <div className="lookpick">
                  <Monitor look={shown} preview={shown !== look} />
                  <div className="lookgrid" role="group" aria-label="Look" style={{ gridTemplateRows: `repeat(${Math.ceil((looks.length + (more ? 1 : 0)) / 2)}, minmax(0, 1fr))` }} onMouseLeave={() => setPeek(null)}>
                    {looks.map((l) => {
                      const still = lookMedia(l).still;
                      return (
                        <button key={l.id} type="button" className="look" aria-pressed={l.id === look?.id} title={l.card || l.blurb} onMouseEnter={() => setPeek(l.id)} onClick={() => pickLook(l)}>
                          {still && <img src={still} alt="" loading="lazy" />}
                          <b>{l.name}</b>
                        </button>
                      );
                    })}
                    {more && (
                      <Link className="look more" to="/s/settings" title="Turn looks on or off in Settings">
                        <Plus {...ICON} />
                        <b>More looks</b>
                      </Link>
                    )}
                  </div>
                </div>
              )}
              <p className="estline">
                <b>{about}</b>
                <span role={price.failed ? "alert" : undefined}>{under}</span>
              </p>
              {owner && (
                <button type="button" role="switch" aria-checked={mode === "ask"} className="swrow" onClick={() => setMode(mode === "ask" ? "auto" : "ask")}>
                  <span>
                    Show me the plan and cast first
                    <small>{mode === "ask" ? "Nothing is filmed until you approve." : "Filming starts as soon as the plan is ready."}</small>
                  </span>
                  <i aria-hidden className="sw" />
                </button>
              )}
              <button type="button" className="btn go make" disabled={!ready || starting} onClick={go}>
                {starting ? (
                  <>
                    <LoaderCircle {...ICON} className="spin" />
                    Starting…
                  </>
                ) : (
                  <>
                    {words.label} {ready && words.most && hooks !== "first" && <small>{words.most}</small>}
                  </>
                )}
              </button>
              {sent.isError && (
                <p role="alert" className="bad">
                  {sent.error.message}
                </p>
              )}
            </aside>
          </div>
        </div>
      </div>
    </>
  );
}
