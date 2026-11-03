"""Brand Studio v6 wireframes: shared pieces. Each board is plain HTML + kit.css, rendered to JPG by render.py.
Pictures: media/*.jpg. Frames from the paid tests are marked "test sample" (Reed's brief); site output is not."""
import json, os, html as H

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "html")
ICONS = json.load(open(os.path.join(HERE, "icons.json")))
BOARDS = []  # (id, title, state, kind, file)

# Site output (not test samples). Everything else in media/ came from the paid tests.
SITE = {"house_marcus_rain", "house_coins_hand", "sheet_gothgf", "fomo_logo", "fomo_home", "fomo_token-up", "fomo_home-rich", "ip_bag_pb"}


def ic(name, cls=""):
    return f'<svg class="i {cls}" viewBox="0 0 24 24">{ICONS[name]}</svg>'


def esc(s):
    return H.escape(s)


def src(name):
    for ext in ("jpg", "png"):
        if os.path.exists(os.path.join(HERE, "media", f"{name}.{ext}")):
            return f"../media/{name}.{ext}"
    raise FileNotFoundError(name)


def media(name, w, h, dur=None, play=False, cls="", tag=True, extra="", style=""):
    """A real frame. tag=True marks test samples as 'test sample' when the picture is big enough to carry it."""
    ts = '<span class="ts">Test sample</span>' if (tag and name not in SITE and w >= 120) else ""
    d = f'<span class="dur">{dur}</span>' if dur else ""
    p = f'<span class="play"><i>{ic("play", "s20")}</i></span>' if play else ""
    return f'<div class="media {cls}" style="width:{w}px;height:{h}px;{style}"><img src="{src(name)}">{ts}{d}{p}{extra}</div>'


def empty_media(w, h, cls="empty", inner=""):
    return f'<div class="media {cls}" style="width:{w}px;height:{h}px">{inner}</div>'


def btn(label, kind="", icon=None, price=None, cls=""):
    i = ic(icon, "s14") if icon else ""
    if price and price[0] in "$0123456789" and not price.startswith("up to"):
        price = "up to " + price
    p = f' <span class="price">· {price}</span>' if price else ""
    return f'<span class="btn {kind} {cls}">{i}{label}{p}</span>'


def chip(label, k=None, icon=None, cls=""):
    i = ic(icon, "s12") if icon else ""
    kk = f'<span class="k">{k}</span> ' if k else ""
    return f'<span class="chip {cls}">{i}{kk}{label}</span>'


def status(kind, words):
    return f'<span class="st {kind}"><span class="dot {kind}"></span>{words}</span>'


# ---------- brands ----------
BRANDS = {
    "Resilia": ('<div class="brandmark" style="background:#24785a">R</div>'),
    "fomo": (f'<div class="brandmark" style="background:#000"><img src="{src("fomo_logo")}" style="width:22px;height:22px"></div>'),
    "Iron Paws": ('<div class="brandmark" style="background:#b5651d">IP</div>'),
}


# ---------- desktop rail ----------
# tree items: (level, kind, label, extra) kind: folder|folderopen|idea|unsorted ; extra: dict(dot=, cnt=, on=, cls=)
def resilia_tree(open_=None, dots=None):
    """The one Resilia tree. open_: the idea that's open (highlighted). dots: {title: dot} overrides so the tree matches the header."""
    ideas = [("Beer gut doctor rant", "work"), ("Bloated after pizza", "need"), ("Why IPAs hit harder", "wait"),
             ("3 signs your gut is angry", "ok"), ("Night-time bloat", "bad"), ("Gut glow-up", "ok")]
    dots = dots or {}
    t = [(0, "folderopen", "Week of 3 Nov", {"cnt": "10"})]
    for n, d in ideas:
        x = {"dot": dots.get(n, d)}
        if n == open_:
            x["on"] = True
        t.append((1, "idea", n, x))
    t.append((1, "idea", "+ 4 more", {"cls": "faint"}))
    t += [(0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9"}), (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
    return t


RESILIA_TREE = resilia_tree("Beer gut doctor rant")


def tree_html(tree):
    out = []
    for lvl, kind, label, x in tree:
        sub = ["", " sub", " sub2", " sub3"][lvl]
        on = " on" if x.get("on") else ""
        cls = " " + x["cls"] if x.get("cls") else ""
        cnt = f'<span class="cnt">{x["cnt"]}</span>' if x.get("cnt") else ""
        if kind == "idea":
            dot = f'<span class="dot {x.get("dot","")}"></span>'
            out.append(f'<div class="ritem idea{sub}{on}{cls}">{dot}<span class="ell">{esc(label)}</span>{cnt}</div>')
        else:
            chev = ic("chevron-down" if kind == "folderopen" else "chevron-right", "s12")
            icon = ic("inbox" if kind == "unsorted" else ("folder-open" if kind == "folderopen" else "folder"), "s14")
            if kind == "unsorted":
                chev = '<span style="width:12px"></span>'
            out.append(f'<div class="ritem{sub}{on}{cls}">{chev}{icon}<span class="ell">{esc(label)}</span>{cnt}</div>')
    return "".join(out)


def rail(brand="Resilia", tree=None, active=None, role="owner", needs=4, extra_top="", tree_html_override=None):
    tree = RESILIA_TREE if tree is None else tree
    a = lambda k: " on" if active == k else ""
    t = tree_html_override if tree_html_override is not None else tree_html(tree)
    studio = ""
    if role == "owner":
        studio = f"""<div class="rhead">Studio</div>
        <div class="ritem{a('needs')}">{ic('inbox','s14')}Needs you<span class="cnt"><span class="badge need">{needs}</span></span></div>
        <div class="ritem{a('prod')}">{ic('clapperboard','s14')}In production</div>
        <div class="ritem{a('usage')}">{ic('chart-column','s14')}Usage</div>
        <div class="ritem{a('team')}">{ic('users','s14')}Team</div>
        <div class="ritem{a('settings')}">{ic('settings','s14')}Settings</div>"""
    else:
        studio = f"""<div class="rhead">Mine</div>
        <div class="ritem{a('myreq')}">{ic('clock','s14')}My requests<span class="cnt"><span class="badge n">1</span></span></div>"""
    acct = '<div class="av">R</div>Reed' if role == "owner" else '<div class="av ed">K</div>Kel'
    return f"""<nav class="rail">
      <div class="brandsw">{BRANDS[brand]}<span>{brand}</span><span class="grow"></span>{ic('chevron-down','s14')}</div>
      <div class="row g2" style="padding:2px 0 6px">
        <span class="btn grow" style="justify-content:flex-start">{ic('plus','s14')}New video<span class="grow"></span><span class="kbd">N</span></span>
        <span class="iconbtn b">{ic('search','s14')}</span>
      </div>
      {extra_top}
      <div class="rhead">Videos<span class="sp"></span><span title="New folder">{ic('folder-plus','s14')}</span></div>
      {t}
      <div class="rhead">Library</div>
      <div class="ritem{a('cast')}">{ic('users','s14')}Cast &amp; places</div>
      <div class="ritem{a('media')}">{ic('image','s14')}Media</div>
      <div class="ritem{a('brand')}">{ic('palette','s14')}Brand kit</div>
      {studio}
      <div class="acct">{acct}<span class="grow"></span>{ic('settings','s14 faint')}</div>
    </nav>"""


# ---------- chat pieces ----------
def m_dir(html_body, time="10:42", extra=""):
    return f"""<div class="msg"><div class="av dir">{ic('sparkles','s12')}</div><div class="body">
      <div class="who">Director<span class="tm">{time}</span>{extra}</div>{html_body}</div></div>"""


def m_me(text, time="10:40", who="Reed", av="R", avcls="", attach=""):
    return f"""<div class="msg me"><div class="av {avcls}">{av}</div><div class="body">
      <div class="who">{who}<span class="tm">{time}</span></div><div class="bubble">{text}</div>{attach}</div></div>"""


def sysline(icon, text):
    return f'<div class="sysline">{ic(icon,"s12")}<span>{text}</span></div>'


def composer(placeholder="Tell the director what to change", typed=False, hint=None, phone=False):
    ph = f'<div class="ph{" typed" if typed else ""}">{placeholder}</div>'
    h = f'<span class="note">{hint}</span>' if hint else ""
    send = '<span class="send">' + ic("arrow-up", "s14") + "</span>" if typed else '<span class="send off">' + ic("arrow-up", "s14") + "</span>"
    return f"""<div class="composer">{ph}<div class="bar"><span class="iconbtn">{ic('upload','s14')}</span>{h}<span class="grow"></span>{send}</div></div>"""


SCENES = [  # (name, frames) for the Resilia "Beer gut doctor rant" (Dr. Pickle, Presenter, 0:58)
    ("Hook", ["drp_1", "drp_3", "drp_2"]),
    ("What beer does", ["pk1", "sd1", "drp_6", "pk1pv"]),
    ("The bloat", ["sd3", "sd2", "drp_5", "drp_6"]),
    ("Worse at night", ["drp_4", "pk3", "pk2", "pk3pv"]),
    ("The fix", ["ug2", "drp_2", "ug1"]),
    ("Ending", ["drp_5", "drp_1"]),
]
UGC_SCENES = [("Hook", ["ugc_1", "ugcb_4"]), ("Pizza nights", ["ugcb_5", "ug1"]), ("The fix", ["ugc_3", "ug2"])]  # Bloated after pizza: 6 clips
SKEL_SCENES = [("3 AM", ["sk1", "pk3", "pk2"]), ("Why at night", ["sk2", "pk1", "sd1", "pk1pv"]), ("The gut", ["sd3", "sd2", "drp_6", "sd1"]),
               ("Water", ["pk3pv", "sk1", "pk2"]), ("The fix", ["ug2", "ug1"]), ("Ending", ["sk2", "pk3"])]  # Night-time bloat: 18 clips
SKIT_SCENES = [("The boxes", ["skit_1", "skit_2", "skit_3"]), ("Caught", ["skit_3", "skit_2", "skit_1", "skit_2"]), ("The talk", ["skit_1", "skit_3", "skit_2"]),
               ("The fix", ["ug2", "skit_3", "ug1", "skit_1"])]  # Caught with the pizza boxes: 14 clips


def filmstrip(states=None, w=22, h=39, current=None, labels=True, scenes=None):
    """states: dict (scene_index, frame_index) -> 'done'|'working'|'todo'|'redo'|'fresh'. default all done."""
    out = []
    for si, (nm, frames) in enumerate(scenes or SCENES):
        fr = []
        for fi, f in enumerate(frames):
            s = (states or {}).get((si, fi), "done") if states is not None else "done"
            if s == "todo":
                fr.append(empty_media(w, h, "empty mini") if w == 22 else empty_media(w, h))
            elif s == "working":
                fr.append(empty_media(w, h, "working mini working"))
            else:
                extra = " " + s if s in ("redo", "fresh") else ""
                fr.append(media(f, w, h, cls="mini" + extra if w == 22 else extra, tag=False))
        lab = f'<div class="lab">{nm}</div>' if labels else ""
        cur = " cur" if current == si else ""
        out.append(f'<div class="scene{cur}"><div class="fr">{"".join(fr)}</div>{lab}</div>')
    return f'<div class="strip">{"".join(out)}</div>'


def progress_states(done_scenes, working=None, todo_from=None, redo=(), scenes=None):
    st = {}
    for si, (_, frames) in enumerate(scenes or SCENES):
        for fi in range(len(frames)):
            if si < done_scenes:
                st[(si, fi)] = "done"
            elif working and (si, fi) in working:
                st[(si, fi)] = "working"
            elif si == done_scenes and todo_from is not None and fi < todo_from:
                st[(si, fi)] = "done"
            else:
                st[(si, fi)] = "todo"
    for k in redo:
        st[k] = "redo"
    return st


def chat_head(title, crumbs, state_html, price_html, locks=None, right="", narrow=False):
    locks = locks if locks is not None else default_locks()
    if narrow:
        return f"""<div class="chathead">
      <div class="row g2"><div class="crumb">{crumbs}</div><span class="grow"></span>{right}</div>
      <div class="row g3"><span class="t-lg ell">{esc(title)}</span></div>
      <div class="row g3">{state_html}<span class="grow"></span>{price_html}</div>
      <div class="locks">{locks}</div></div>"""
    return f"""<div class="chathead">
      <div class="row g2"><div class="crumb">{crumbs}</div><span class="grow"></span>{right}</div>
      <div class="row g3"><span class="t-lg ell" style="max-width:330px">{esc(title)}</span>{state_html}<span class="grow"></span>{price_html}</div>
      <div class="locks">{locks}</div></div>"""


def default_locks(cast=True, style=True, extra=None, more="+3", fmt="Presenter", sty="Dr. Pickle", castn="Dr. Pickle", length="about 60 s"):
    l = [
        chip(f"{fmt} · {sty}", None, "lock" if style else "clapperboard", "lockd" if style else ""),
        chip(castn, "Cast", "lock" if cast else None, "lockd" if cast else ""),
        chip(length, "Length"),
    ]
    m = chip(f"Locks {more}", None, "sliders-horizontal") if more else ""
    return "".join(l) + (extra or "") + m


def price_owner(upto="up to $16.86", spent="$6.12 spent"):
    sp = f"{spent} · " if spent and not spent.endswith(("·", "to")) else (spent + " " if spent else "")
    return f'<span class="t-sm muted num">{sp}<b class="w5" style="color:var(--text)">{upto}</b></span>'


def price_editor(upto="up to 164 credits", spent="60 credits used"):
    sp = f"{spent} · " if spent and not spent.endswith(("·", "to")) else (spent + " " if spent else "")
    return f'<span class="t-sm muted num">{sp}<b class="w5" style="color:var(--text)">{upto}</b></span>'


def panel(tabs_on="Cut", body="", tabs=None, right=""):
    tabs = tabs or [("Cut", None), ("Clips", "24"), ("Cast", "2"), ("Plan", None), ("Script", None)]
    t = "".join(f'<span class="{"on" if n == tabs_on else ""}">{n}{f" <span class=n>{c}</span>" if c else ""}</span>' for n, c in tabs)
    return f"""<section class="panel"><div class="tabs" style="background:var(--surface);align-items:center">{t}<span style="flex:1"></span>{right}</div>
      <div class="panelbody">{body}</div></section>"""


def player(name, w, h, t="0:21", total="0:58", pct=36, extra=""):
    ts = '<span class="ts" style="position:absolute;left:10px;top:10px;font-size:11px;font-weight:600;color:#fff;background:rgb(0 0 0 / .62);padding:2px 6px;border-radius:3px">Test sample</span>' if name not in SITE else ""
    return f"""<div class="player" style="width:{w}px;height:{h}px"><img src="{src(name)}">{ts}{extra}
      <div class="ctrl"><div class="scrub"><i style="width:{pct}%"></i></div>
      <div class="r">{ic('pause','s14')}<span class="num">{t} / {total}</span><span class="grow"></span>{ic('volume-2','s14')}{ic('maximize-2','s14')}</div></div></div>"""


# ---------- phone ----------
def phone_status():
    return f'<div class="status"><span>9:41</span><span class="row g1">{ic("wifi-off","s14") if False else ""}<svg width="18" height="11" viewBox="0 0 18 11"><rect x="0" y="7" width="3" height="4" rx="1" fill="#1b1c1f"/><rect x="5" y="5" width="3" height="6" rx="1" fill="#1b1c1f"/><rect x="10" y="2.5" width="3" height="8.5" rx="1" fill="#1b1c1f"/><rect x="15" y="0" width="3" height="11" rx="1" fill="#1b1c1f"/></svg><svg width="26" height="12" viewBox="0 0 26 12"><rect x=".5" y=".5" width="22" height="11" rx="3" fill="none" stroke="#1b1c1f" opacity=".4"/><rect x="2" y="2" width="17" height="8" rx="2" fill="#1b1c1f"/></svg></span></div>'


def phone_tabs(on="Videos", needs=4, role="owner"):
    items = [("Videos", "film"), ("Library", "users"), ("Needs you" if role == "owner" else "Requests", "inbox"), ("More", "ellipsis")]
    out = []
    for n, i in items:
        b = f'<span class="badge need">{needs}</span>' if n == "Needs you" and needs else ""
        out.append(f'<span class="{"on" if n == on else ""}">{ic(i,"s20")}{n}{b}</span>')
    return f'<div class="ptabs">{"".join(out)}</div>'


# ---------- board writer ----------
def board(bid, title, state, inner, kind="d", note="", h=900):
    """kind d = desktop 1440x900, p = phone 390x844, s = sheet (1440 wide, any height)."""
    os.makedirs(OUT, exist_ok=True)
    size = {"d": "1440", "p": "390", "s": "1440 · sheet"}[kind]
    cls = {"d": "screen d", "p": "screen p", "s": "sheetboard"}[kind]
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../kit.css"></head><body>
<div class="board"><div class="label"><b>{bid}</b><span>{esc(title)}</span><span class="tag">{esc(state)}</span><span class="sp"></span><span class="tag">{("" if kind == "p" else "Pictures: paid test samples unless shown as site output") if "media/" in inner and any(m in inner for m in ("drp_","ugc","skit","px","sk1","sk2","cl1","zd1","pk1","sd1","still_")) else ""}</span><span class="tag">{size}</span></div>
<div class="{cls}"{f' data-h="{h}" style="height:{h}px"' if kind == "s" else ""}>{inner}</div></div></body></html>"""
    fn = f"{bid}.html"
    open(os.path.join(OUT, fn), "w").write(doc)
    BOARDS.append((bid, title, state, kind, note))


# ---------- ask card ----------
WAYS = {
    "upload": ("upload", "Upload", "A photo, a still or a clip"),
    "reply": ("message-square", "Reply", "Tell me in words"),
}


def ask_card(kind, q, why, saved=None, saved_label="Saved in Resilia", ways=("upload", "reply", "generate"), gen=("Generate options", "3 options · up to $0.24"),
             state="open", sel=None, options=None, body_extra="", foot=None, head_right="", held_note=None):
    """kind: the small header words. saved: list of (img, name, sub). options: generated options (img, name, sub)."""
    cls = {"open": "", "done": " done", "held": " held"}.get(state, "")
    hd_icon = {"open": "circle-question-mark", "done": "check", "held": "clock"}[state]
    parts = [f'<div class="q">{q}</div>']
    if why:
        parts.append(f'<div class="why">{why}</div>')
    if saved:
        o = "".join(f'<div class="opt{" sel" if sel == i else ""}">{media(im, 96, 128, tag=False)}<span class="nm">{n}</span><span class="t-xs muted">{s}</span></div>' for i, (im, n, s) in enumerate(saved))
        parts.append(f'<div class="col g2"><span class="sec">{saved_label}</span><div class="opts">{o}</div></div>')
    if options:
        o = "".join(f'<div class="opt{" sel" if sel == ("g", i) else ""}">{media(im, 96, 128) if im else empty_media(96,128,"working")}<span class="nm">{n}</span><span class="t-xs muted">{s}</span></div>' for i, (im, n, s) in enumerate(options))
        parts.append(f'<div class="col g2"><span class="sec">Made for this video · not saved to the brand</span><div class="opts">{o}</div></div>')
    if body_extra:
        parts.append(body_extra)
    if ways:
        w = []
        for k in ways:
            if k == "generate":
                w.append(f'<div class="way">{ic("wand-sparkles","s14")}<div><span class="w6">{gen[0]}</span><small>{gen[1]}</small></div></div>')
            else:
                i, n, s = WAYS[k]
                w.append(f'<div class="way{" dashed" if k == "upload" else ""}">{ic(i,"s14")}<div><span class="w6">{n}</span><small>{s}</small></div></div>')
        parts.append(f'<div class="ways">{"".join(w)}</div>')
    if held_note:
        parts.append(held_note)
    f = f'<div class="ft">{foot}</div>' if foot else ""
    return f"""<div class="ask{cls}"><div class="ahd">{ic(hd_icon,"s14")}<span>{kind}</span><span class="grow"></span>{head_right}</div>
      <div class="abd">{"".join(parts)}</div>{f.replace('class="ft"','class="ft" style="padding:10px 14px;border-top:1px solid var(--border);display:flex;gap:8px;align-items:center"')}</div>"""


def treatment_card(compact=False):
    beats = [("Hook", "0–2 s", "The glowing spine and “Your gut after the weekend…”", "Stops the scroll on a gross, bright picture"),
             ("What beer does", "2–14 s", "Beer pours through the see-through body", "Shows the cause, one picture per line"),
             ("The bloat", "14–27 s", "The gut swells green; Dr. Pickle points", "The problem on the body"),
             ("Worse at night", "27–40 s", "He tosses in bed, belly glowing", "A feeling people know"),
             ("The fix", "40–52 s", "The Resilia capsule, then the gut calms", "Product at the turn"),
             ("Ending", "52–58 s", "Dr. Pickle: “Link in my bio.”", "Names the brand and where")]
    rows = "".join(f'<div class="row g3 start t-sm" style="padding:6px 0;border-top:1px solid var(--border)"><span class="w6" style="width:104px;flex:none">{b}</span><span class="muted num" style="width:54px;flex:none">{t}</span><span class="grow">{p}<br><span class="muted t-xs">{why}</span></span></div>' for b, t, p, why in beats[: (3 if compact else 6)])
    more = '<div class="t-xs muted" style="padding-top:6px">+ 3 more beats</div>' if compact else ""
    return f"""<div class="card"><div class="hd"><span class="w6 t-sm">Treatment</span><span class="t-xs muted">Dr. Pickle style guide · Presenter format</span></div>
      <div class="bd col g2">
        <p class="t-sm"><b class="w6">In one line:</b> a doctor who’s sick of your excuses shows what the weekend does to your gut, then hands you the fix.</p>
        <p class="t-sm"><b class="w6">Why it holds:</b> a gross, glowing body in the first second, a rant that never pauses, and every line acted out behind him.</p>
        <div class="col">{rows}{more}</div></div></div>"""
