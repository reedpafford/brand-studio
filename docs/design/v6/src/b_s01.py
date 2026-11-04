"""S0 the frame and folder tree; S1 brand home (an open folder)."""
from lib import *

IDEAS = [  # title, frame, status kind, status words, style, length, who, when, price(owner), credits(editor)
    ("Beer gut doctor rant", "drp_2", "work", "Working · 14 of 24", "Dr. Pickle", "60 s", "Reed", "10 min ago", "up to $16.86", "up to 164 cr"),
    ("Bloated after pizza", "ugc_1", "need", "Needs you · 1 question", "UGC", "30 s", "Reed", "1 h ago", "$0.42 so far", "4 cr so far"),
    ("Why IPAs hit harder", "drp_3", "wait", "Waiting for your OK", "Dr. Pickle", "58 s", "Kel", "2 h ago", "$16.30", "159 cr"),
    ("3 signs your gut is angry", "sk1", "ok", "Delivered", "Skeleton", "45 s", "Kel", "yesterday", "$7.20", "70 cr"),
    ("Night-time bloat", "pk3", "bad", "Needs a fix", "Skeleton", "45 s", "Reed", "yesterday", "$1.20 so far", "12 cr so far"),
    ("Gut glow-up", "cl1", "ok", "Delivered", "Claymation", "40 s", "Sam", "2 days ago", "$6.10", "59 cr"),
    ("The 3 AM party", "px1", "ok", "Delivered", "Disney Pixar", "35 s", "Reed", "3 days ago", "$9.40", "91 cr"),
    ("Your gut on a Friday", "zd1", "ok", "Delivered", "Zack D", "50 s", "Kel", "4 days ago", "$5.80", "56 cr"),
    ("Morning-after reset", "px2", "ok", "Delivered", "Disney Pixar", "30 s", "Sam", "5 days ago", "$8.10", "79 cr"),
    ("Pint vs capsule", "sd1", "stop", "Stopped", "Dr. Pickle", "60 s", "Reed", "6 days ago", "$3.10 so far", "30 cr so far"),
]


def icard(i, owner=True, sel=False, check=False):
    t, f, k, s, sty, ln, who, when, p, c = i
    if not owner:
        s = s.replace("Waiting for your OK", "Waiting for the owner")
    box = f'<span class="selbox check{" on" if sel else ""}">{ic("check","s12") if sel else ""}</span>' if check else ""
    overlay = ""
    if k == "work":
        overlay = '<div style="position:absolute;left:8px;right:8px;bottom:8px" class="prog"><i style="width:58%"></i></div>'
    return f'''<div class="icard{" selected" if sel else ""}">{box}{media(f, 212, 290, extra=overlay)}
      <div class="col g1"><span class="t">{esc(t)}</span>{status(k, s)}
      <span class="m">{sty} · {ln} · {who} · {when}</span><span class="m num">{p if owner else c}</span></div></div>'''


def folder_head(name, n, owner=True, right_extra="", sub=None, primary=True):
    sub = sub or f"{n} video ideas · 2 need you"
    return f'''<div class="ptop" style="height:56px">{'<div class="crumb">Resilia ' + ic("chevron-right","s12") + ' <b>' + name + '</b></div>'}<span class="t-sm muted">{sub}</span>
      <span class="grow"></span>{right_extra}<span class="iconbtn">{ic("ellipsis","s14")}</span>{btn("New video", "primary lg" if primary else "lg", "plus")}</div>'''


def filters(on="All", counts=(10, 2, 2, 5), search="Search this folder", extra="", view="cards"):
    labels = ["All", "Needs you", "Working", "Delivered"]
    seg = "".join(f'<span class="{"on" if l == on else ""}">{l} <span class="faint">{c}</span></span>' for l, c in zip(labels, counts))
    return f'''<div class="row g3" style="padding:16px 24px 0"><div class="seg">{seg}</div><div class="input" style="width:260px;height:32px">{ic("search","s14")}{search}</div>
      <span class="grow"></span>{extra}{chip("Newest", "Sort", "list-filter")}<div class="seg"><span class="{"on" if view == "cards" else ""}">{ic("layers","s14")}</span><span class="{"on" if view == "list" else ""}">{ic("list-filter","s14")}</span></div></div>'''


def grid(items, owner=True, sel=(), check=False):
    return f'<div class="ideas" style="padding:20px 24px">{"".join(icard(i, owner, n in sel, check) for n, i in enumerate(items))}</div>'


def home(owner=True):
    return rail(active=None, role="owner" if owner else "editor", tree=FOLDER_TREE) + f'<main class="main">{folder_head("Week of 3 Nov", 10)}{filters()}{grid(IDEAS, owner)}</main>'


FOLDER_TREE = [(0, "folderopen", "Week of 3 Nov", {"cnt": "10", "on": True}), (1, "idea", "Beer gut doctor rant", {"dot": "work"}), (1, "idea", "Bloated after pizza", {"dot": "need"}),
               (1, "idea", "Why IPAs hit harder", {"dot": "wait"}), (1, "idea", "3 signs your gut is angry", {"dot": "ok"}), (1, "idea", "Night-time bloat", {"dot": "bad"}),
               (1, "idea", "+ 5 more", {"cls": "faint"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9"}),
               (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]


# ---------- S1 boards ----------
def s1_loading():
    sk = lambda w, h=12: f'<div class="skel" style="width:{w}px;height:{h}px"></div>'
    cards = "".join(f'<div class="col g2"><div class="skel" style="width:212px;height:290px;border-radius:6px"></div>{sk(160)}{sk(110)}</div>' for _ in range(10))
    return rail(tree=FOLDER_TREE) + f'<main class="main">{folder_head("Week of 3 Nov", 10, sub="Loading…")}{filters(counts=("", "", "", ""))}<div class="ideas" style="padding:20px 24px">{cards}</div></main>'


def s1_newbrand():
    steps = [("check", True, "Name and colour", "Resilia · green"), ("image", False, "Logo", "Shown on products and in endings"),
             ("users", False, "Characters", "People the director can cast without asking"), ("package", False, "Products", "The real bottle or bag, so labels read right"),
             ("map-pin", False, "Places", "Rooms and streets that recur"), ("mic", False, "Voices and presenters", "For narrated and presenter videos"),
             ("file-text", False, "Tone and rules", "What the brand never says, its end line")]
    rows = "".join(f'<div class="lrow" style="padding:12px 16px"><span class="check{" on" if d else ""}">{ic("check","s12") if d else ""}</span>{ic(i,"s16 muted")}<div class="col grow"><span class="w6">{t}</span><span class="t-sm muted">{s}</span></div>{"" if d else btn("Add")}</div>' for i, d, t, s in steps)
    tree = [(0, "unsorted", "Unsorted", {"cnt": "0", "on": True})]
    body = f'''<div style="padding:48px 0;display:flex;justify-content:center"><div class="col g5" style="width:640px">
      <div class="col g2"><span class="t-2xl">Set up Resilia</span><span class="t-md muted">The more the brand knows, the less the director has to ask. You can make a video now and add these later.</span></div>
      <div class="list">{rows}</div>
      <div class="row g3">{btn("Import from the brand’s website", "lg", "globe")}<span class="grow"></span>{btn("Make the first video", "primary lg", "plus")}</div>
      <span class="t-sm muted">Each brand is separate: nothing saved here shows up in fomo or Iron Paws.</span></div></div>'''
    return rail(tree=tree, needs=0) + f'<main class="main"><div class="ptop"><div class="crumb"><b>Resilia</b></div><span class="t-sm muted">New brand</span></div>{body}</main>'


def s1_emptyfolder():
    body = f'''<div class="col center g3" style="flex:1;text-align:center">
      <div class="row g2" style="opacity:.9">{empty_media(72,128)}{empty_media(72,128)}{empty_media(72,128)}</div>
      <span class="t-xl">Nothing in Black Friday yet</span><span class="t-md muted" style="max-width:420px">Start a video here, or drag ideas in from another folder in the list on the left.</span>
      <div class="row g2">{btn("New video in Black Friday", "primary lg", "plus")}{btn("New folder inside", "lg", "folder-plus")}</div></div>'''
    tree = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9"}),
            (0, "folderopen", "Black Friday", {"cnt": "0", "on": True}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
    return rail(tree=tree) + f'<main class="main">{folder_head("Black Friday", 0, sub="Empty", primary=False)}{body}</main>'


def s1_many(owner=True):
    rows_data = [("drp_1", "Dr. Pickle on hangovers", "ok", "Delivered", "58 s", "Reed", "3 Nov", "$9.10"),
                 ("drp_2", "Beer gut doctor rant · v2", "work", "Working", "60 s", "Reed", "3 Nov", "up to $16.86"),
                 ("drp_4", "3 AM bloat, the doctor’s take", "need", "Needs you", "55 s", "Kel", "2 Nov", "$0.80 so far"),
                 ("drp_5", "IPA vs lager", "ok", "Delivered", "62 s", "Sam", "2 Nov", "$10.40"),
                 ("drp_6", "Gut bacteria, explained angrily", "ok", "Delivered", "71 s", "Kel", "1 Nov", "$12.20"),
                 ("sd1", "The couch potato skeleton", "ok", "Delivered", "48 s", "Reed", "1 Nov", "$8.30"),
                 ("sd3", "Why your belly glows", "bad", "Needs a fix", "50 s", "Kel", "31 Oct", "$2.10 so far"),
                 ("drp_3", "Spine on fire", "ok", "Delivered", "52 s", "Sam", "31 Oct", "$8.90"),
                 ("pk1", "Coffee won’t save you", "ok", "Delivered", "45 s", "Reed", "30 Oct", "$7.70"),
                 ("pk2", "Night sweats", "stop", "Stopped", "60 s", "Kel", "30 Oct", "$4.00 so far"),
                 ("sd2", "Gut lining 101", "ok", "Delivered", "66 s", "Sam", "29 Oct", "$11.30"),
                 ("drp_1", "Weekend warrior", "ok", "Delivered", "54 s", "Reed", "29 Oct", "$9.00"),
                 ("pk3", "Pillow talk", "ok", "Delivered", "47 s", "Kel", "28 Oct", "$8.10")]
    hd = '<div class="lrow hd"><span class="check"></span><span style="width:38px"></span><span class="grow">Idea</span><span style="width:150px">Status</span><span style="width:70px">Length</span><span style="width:90px">Made by</span><span style="width:80px">Updated ' + ic("chevron-down", "s12") + '</span><span style="width:110px;text-align:right">' + ("Cost" if owner else "Credits") + '</span><span style="width:24px"></span></div>'
    rows = "".join(f'<div class="lrow"><span class="check"></span>{media(f,22,39,tag=False)}<span class="grow w5 ell">{t}</span><span style="width:150px">{status(k,s)}</span><span class="muted num" style="width:70px">{l}</span><span style="width:90px" class="muted">{w}</span><span class="muted" style="width:80px">{d}</span><span class="num" style="width:110px;text-align:right">{p}</span><span class="iconbtn" style="width:24px;height:24px">{ic("ellipsis","s14")}</span></div>' for f, t, k, s, l, w, d, p in rows_data)
    tree = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folderopen", "Dr. Pickle rants", {"cnt": "124", "on": True}), (1, "folder", "Hangovers", {"cnt": "31"}), (1, "folder", "Gut science", {"cnt": "42"}),
            (0, "folder", "UGC testimonials", {"cnt": "9"}), (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
    filt = filters(counts=(124, 3, 1, 112), search="Search 124 ideas", extra=chip("Anyone", "Made by"), view="list").replace("width:260px", "width:200px")
    return rail(tree=tree) + f'<main class="main">{folder_head("Dr. Pickle rants", 124, sub="124 video ideas · 2 folders inside")}{filt}<div style="padding:16px 24px"><div class="list">{hd}{rows}</div><div class="row between t-sm muted" style="padding:10px 4px"><span>Showing 1–13 of 124</span><span>Scroll for more · the list loads as you go</span></div></div></main>'


def s1_archived():
    arch = [("Old hangover cure", "drp_4", "stop", "Archived 28 Oct", "Dr. Pickle", "60 s", "Kel", "28 Oct", "$4.10", "40 cr"),
            ("Draft: gut quiz", "sk2", "stop", "Archived 25 Oct", "Skeleton", "—", "Reed", "25 Oct", "$0.00", "0 cr")]
    items = "".join(f'<div class="icard" style="opacity:.75">{media(f,212,290)}<div class="col g1"><span class="t">{t}</span>{status(k,s)}<span class="m">{sty} · {who}</span><div class="row g2" style="margin-top:4px">{btn("Restore","","rotate-ccw")}</div></div></div>' for t, f, k, s, sty, ln, who, w, p, c in arch)
    return rail(tree=FOLDER_TREE) + f'''<main class="main">{folder_head("Week of 3 Nov", 10)}<div class="row g3" style="padding:16px 24px 0">{btn("Back to the folder","","arrow-left")}<span class="t-lg">Archived</span><span class="t-sm muted">2 ideas · kept, not shown in the folder · their files stay downloadable</span></div>
      <div class="ideas" style="padding:20px 24px">{items}</div></main>'''


def s1_select():
    bar = f'''<div style="position:absolute;left:50%;bottom:24px;transform:translateX(-50%);display:flex;gap:10px;align-items:center;background:var(--ink);color:#fff;border-radius:10px;padding:8px 8px 8px 16px;box-shadow:var(--shadow-overlay)">
      <span class="t-sm w5">3 selected</span><span class="btn" style="background:#2c2e34;border-color:#3a3c43;color:#fff">{ic("folder","s14")}Move to…</span><span class="btn" style="background:#2c2e34;border-color:#3a3c43;color:#fff">{ic("archive","s14")}Archive</span><span class="iconbtn" style="color:#fff">{ic("x","s14")}</span></div>'''
    menu = f'''<div class="menu" style="left:860px;bottom:76px;width:240px"><div class="mi"><span class="t-xs muted">Move 3 ideas to</span></div><div class="mi">{ic("folder","s14")}Dr. Pickle rants</div><div class="mi" style="padding-left:24px">{ic("folder","s14")}Hangovers</div><div class="mi on">{ic("folder","s14")}UGC testimonials</div><div class="mi">{ic("folder","s14")}Black Friday</div><div class="mi">{ic("inbox","s14")}Unsorted</div><div class="sepm"></div><div class="mi">{ic("folder-plus","s14")}New folder…</div></div>'''
    return rail(tree=FOLDER_TREE) + f'<main class="main" style="position:relative">{folder_head("Week of 3 Nov", 10)}{filters()}{grid(IDEAS, True, sel=(1, 3, 5), check=True)}{bar}{menu}</main>'


def s1_editor():
    return home(False)


board("S1-01", "Brand home: an open folder", "Loading", s1_loading())
board("S1-02", "Brand home: an open folder", "Brand-new brand · set-up list", s1_newbrand())
board("S1-03", "Brand home: an open folder", "Empty folder", s1_emptyfolder())
board("S1-04", "Brand home: an open folder", "Normal folder · owner", home(True))
board("S1-05", "Brand home: an open folder", "124 ideas · list view, sort, filter, search", s1_many())
board("S1-06", "Brand home: an open folder", "Archived ideas", s1_archived())
board("S1-07", "Brand home: an open folder", "Several selected · Move, Archive", s1_select())
board("S1-08", "Brand home: an open folder", "Normal folder · editor (credits)", s1_editor())


# ---------- S0: the tree's states, as a sheet of rails ----------
def rail_only(caption, r, note=""):
    return f'<div class="col g2"><div class="col"><span class="t-sm w6">{caption}</span><span class="t-xs muted" style="min-height:16px">{note}</span></div><div class="screen" style="width:248px;height:820px;display:flex;border:1px solid var(--border);border-radius:8px">{r}</div></div>'


nofolders = rail(tree=[(0, "unsorted", "Unsorted", {"cnt": "3", "on": True}), (1, "idea", "First test video", {"dot": "ok"}), (1, "idea", "Hangover rant", {"dot": "work"}), (1, "idea", "Try UGC", {"dot": "need"})], needs=1,
                 extra_top="")
nested = rail(tree=[(0, "folderopen", "Dr. Pickle rants", {"cnt": "124"}), (1, "folderopen", "Hangovers", {"cnt": "31"}), (2, "folder", "Weekend", {"cnt": "12"}), (2, "idea", "Dr. Pickle on hangovers", {"dot": "ok", "on": True}), (2, "idea", "Weekend warrior", {"dot": "ok"}),
                     (1, "folder", "Gut science", {"cnt": "42"}), (0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "UGC testimonials", {"cnt": "9"}), (0, "unsorted", "Unsorted", {"cnt": "2"})])
drag_tree = [(0, "folderopen", "Week of 3 Nov", {"cnt": "10"}), (1, "idea", "Beer gut doctor rant", {"dot": "work"}), (1, "idea", "Bloated after pizza", {"dot": "need", "cls": "faint"}),
             (1, "idea", "Why IPAs hit harder", {"dot": "wait"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9", "cls": "drop"}), (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
drag = rail(tree=drag_tree).replace('</nav>', f'<div class="ghostdrag" style="left:70px;top:286px">{media("ugc_1",18,32,tag=False)}Bloated after pizza</div></nav>')
ren_tree = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials|", {"cnt": "", "cls": "renaming"}), (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
ren = rail(tree=ren_tree).replace("UGC testimonials|", 'UGC testimonials<span style="display:inline-block;width:1px;height:14px;background:var(--accent);margin-left:1px;vertical-align:middle"></span>')
del_tree = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9"}), (0, "unsorted", "Unsorted", {"cnt": "5", "on": True}), (1, "idea", "Last-minute gift", {"dot": "ok"}), (1, "idea", "Cyber Monday gut", {"dot": "ok"}), (1, "idea", "Deal of the year", {"dot": "stop"})]
dele = rail(tree=del_tree).replace('</nav>', f'<div class="toast" style="left:124px;bottom:60px;width:232px;flex-wrap:wrap;gap:6px"><span>Deleted “Black Friday”. Its 3 ideas moved to Unsorted.</span><b>Undo</b></div></nav>')
editor_rail = rail(role="editor", tree=FOLDER_TREE)
menu_rail = rail(tree=FOLDER_TREE).replace('</nav>', f'<div class="menu" style="left:60px;top:430px;width:180px"><div class="mi">{ic("plus","s14")}New video here</div><div class="mi">{ic("folder-plus","s14")}New folder inside</div><div class="mi on">{ic("pencil","s14")}Rename</div><div class="mi">{ic("arrow-right-left","s14")}Move to…</div><div class="sepm"></div><div class="mi bad-t">{ic("trash","s14")}Delete folder…</div></div></nav>')

legend = "".join(f'<div class="row g2 t-sm">{status(k, w)}<span class="muted">{d}</span></div>' for k, w, d in [
    ("work", "Working", "the director is making it; the header adds what it’s doing: “Working · revising”"), ("need", "Needs you", "a question or a fix is waiting"), ("wait", "Waiting for the owner", "a budget OK is waiting"),
    ("bad", "Needs a fix", "a step failed; the fix is one press"), ("ok", "Delivered", "the cut is ready"), ("stop", "Stopped", "a person stopped it")])
board("S0-01", "Frame and folder tree", "Tree states: none, nested, drag, rename, menu, delete + Undo, editor",
      f'''<div class="col g2" style="margin-bottom:24px"><span class="t-2xl">The folder tree</span><span class="t-sm muted">Free folders the person makes and names, inside each brand. Folders can hold folders. Every idea sits in one folder, or in Unsorted.</span></div>
      <div class="row g6 start">{rail_only("No folders yet", nofolders, "only Unsorted")}{rail_only("Folders inside folders", nested)}{rail_only("Dragging an idea", drag, "drop target lights up")}{rail_only("Renaming", ren, "type, Enter to save")}{rail_only("Folder menu", menu_rail, "right-click or ⋯")}</div>
      <div class="row g6 start" style="margin-top:32px">{rail_only("Deleting a folder that holds ideas", dele, "ideas move to Unsorted, with Undo")}{rail_only("Editor", editor_rail, "no Studio; My requests instead")}
      <div class="col g3" style="width:520px;margin-top:40px"><span class="t-lg">Status dots</span><span class="t-sm muted">A dot plus words wherever an idea is listed. In the tree the dot stands alone; the words show on hover and in the folder.</span><div class="col g2">{legend}</div></div></div>''', "s", h=1820)
