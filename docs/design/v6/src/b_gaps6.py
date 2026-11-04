"""S-gaps-06: five open-folder details the boards leave open (the brand-home build, #1304, 4 Nov). For Reed's yes or no."""
from lib import *
from b_s01 import IDEAS
from b_phone import BACK

W = 1344
ASK = ("need", "For Reed: yes or no?")


def cell(n, title, ask, drawn, verdicts, w=W):
    v = "".join(f'<div class="row g2 t-sm start"><span class="tag {k}" style="flex:none">{t}</span><span class="muted">{note}</span></div>' for k, t, note in verdicts)
    return f'''<div class="col g3" style="width:{w}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="col g2">{v}</div></div>'''


def side(label, body, note="", w=None):
    nt = f'<span class="t-xs muted">{note}</span>' if note else ""
    ww = f"width:{w}px;" if w else ""
    return f'<div class="col g2" style="flex:none;{ww}"><span class="t-xs w6 muted">{label}</span>{body}{nt}</div>'


def phone(top, body, bottom="", h=600, tabs=True):
    """A 390 phone at 1x, cut off at h. (class order "p screen" keeps render.py from treating the sheet as a phone board.)"""
    t = phone_tabs() if tabs is True else (tabs or "")
    return f'''<div class="p screen" style="height:{h}px;border:1px solid var(--border);border-radius:14px;flex:none">{phone_status()}{top}
      <div class="pbody" style="position:relative">{body}</div>{bottom}{t}<div class="home-ind"><i></i></div></div>'''


def ptop(left, title, right="", sub=None):
    s = f'<span class="t-xs muted">{sub}</span>' if sub else ""
    return f'<div class="ptopbar">{left}<div class="col grow" style="min-width:0"><span class="w6 ell">{title}</span>{s}</div>{right}</div>'


SEARCH = f'<span class="iconbtn">{ic("search","s20")}</span>'
MORE = f'<span class="iconbtn">{ic("ellipsis","s20")}</span>'
MORE_ON = f'<span class="iconbtn" style="background:var(--surface-2);color:var(--text)">{ic("ellipsis","s20")}</span>'
FTOP = lambda right=SEARCH + MORE: ptop(BACK, "Week of 3 Nov", right, "Resilia · 10 ideas · 2 need you")
PTABS = '<div class="row g2" style="padding:10px 14px;overflow:hidden;flex:none"><div class="seg" style="white-space:nowrap"><span class="on">All</span><span>Needs you 2</span><span>Working 2</span><span>Delivered 5</span></div></div>'


def pcard(i, box=None):
    t, f, k, s, sty, ln, who, when, p, c = i
    b = ""
    if box == "on":
        b = f'<span class="selbox check on">{ic("check","s12")}</span>'
    elif box == "off":
        b = '<span class="selbox check"></span>'
    return f'<div class="icard{" selected" if box == "on" else ""}">{b}{media(f, 175, 230)}<div class="col g1"><span class="t" style="font-size:14px">{t}</span>{status(k, s.split(" · ")[0])}<span class="m">{sty} · {p}</span></div></div>'


def pcards(items, boxes=None):
    boxes = boxes or [None] * len(items)
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px 12px;padding:4px 14px;flex:none">{"".join(pcard(i, b) for i, b in zip(items, boxes))}</div>'


DARKBTN = 'class="btn" style="background:#2c2e34;border-color:#3a3c43;color:#fff"'


def selbar(n, phone_=False, menu=""):
    move = f'<span style="position:relative;display:inline-flex"><span {DARKBTN}>{ic("folder","s14")}Move to…</span>{menu}</span>'
    arch = f'<span {DARKBTN}>{ic("archive","s14")}Archive</span>'
    x = f'<span class="iconbtn" style="color:#fff">{ic("x","s14")}</span>'
    if phone_:
        return f'<div style="flex:none;display:flex;gap:8px;align-items:center;background:var(--ink);color:#fff;padding:10px 10px 10px 16px;height:72px"><span class="t-sm w5 grow">{n} selected</span>{move}{arch}{x}</div>'
    return f'<div style="display:inline-flex;gap:10px;align-items:center;background:var(--ink);color:#fff;border-radius:10px;padding:8px 8px 8px 16px;box-shadow:var(--shadow-overlay)"><span class="t-sm w5">{n} selected</span>{move}{arch}{x}</div>'


def move_menu(n, style, tall=False):
    hh = ' style="height:40px;font-size:14px"' if tall else ""
    hhi = ' style="height:40px;font-size:14px;padding-left:28px"' if tall else ' style="padding-left:28px"'
    rows = [("folder", "Dr. Pickle rants", False), ("folder", "Hangovers", True), ("folder", "Gut science", True), ("folder", "UGC testimonials", False), ("folder", "Black Friday", False), ("inbox", "Unsorted", False)]
    r = "".join(f'<div class="mi"{hhi if sub else hh}>{ic(i,"s14")}{t}</div>' for i, t, sub in rows)
    return f'''<div class="menu" style="color:var(--text);z-index:10;{style}"><div class="mi"><span class="t-xs muted">Move {n} ideas to</span></div>{r}<div class="sepm"></div><div class="mi"{hh}>{ic("folder-plus","s14")}New folder…</div></div>'''


# ---------- 7. The list's Status column ----------
rows7 = [("drp_1", "Dr. Pickle on hangovers", "ok", "Delivered", "58 s", "Reed", "3 Nov", "$9.10"),
         ("drp_2", "Beer gut doctor rant · v2", "work", "Working · 14 of 24", "60 s", "Reed", "3 Nov", "up to $16.86"),
         ("drp_4", "3 AM bloat, the doctor’s take", "need", "Needs you · Check the scene plan", "55 s", "Kel", "2 Nov", "$0.80 so far"),
         ("drp_5", "IPA vs lager", "need", "Needs you · 1 question", "62 s", "Sam", "2 Nov", "$0.42 so far"),
         ("sd3", "Why your belly glows", "bad", "Needs a fix · Stopped at clip 4", "50 s", "Kel", "31 Oct", "$2.10 so far"),
         ("pk2", "Night sweats", "stop", "Stopped · by Kel at 16:02", "60 s", "Kel", "30 Oct", "$4.00 so far"),
         ("drp_3", "Spine on fire", "ok", "Delivered", "52 s", "Sam", "31 Oct", "$8.90")]
SW = 230
hd7 = f'<div class="lrow hd"><span class="check"></span><span style="width:38px"></span><span class="grow">Idea</span><span style="width:{SW}px" class="row g2">Status<span class="tag new">{SW} px</span></span><span style="width:70px">Length</span><span style="width:90px">Made by</span><span style="width:80px">Updated {ic("chevron-down","s12")}</span><span style="width:110px;text-align:right">Cost</span><span style="width:24px"></span></div>'
body7 = "".join(f'<div class="lrow"><span class="check"></span>{media(f,22,39,tag=False)}<span class="grow w5 ell">{t}</span><span style="width:{SW}px;background:var(--accent-soft);margin:-8px 0;padding:8px 0 8px 6px;display:flex;align-items:center;align-self:stretch" class="ell">{status(k,s)}</span><span class="muted num" style="width:70px">{l}</span><span style="width:90px" class="muted">{w}</span><span class="muted" style="width:80px">{d}</span><span class="num" style="width:110px;text-align:right">{p}</span><span class="iconbtn" style="width:24px;height:24px">{ic("ellipsis","s14")}</span></div>' for f, t, k, s, l, w, d, p in rows7)
g7 = f'''<div class="col g4">{side("Desktop · S1-05’s list at its real width, Status at 230 px (shaded)", f'<div class="list" style="width:1144px">{hd7}{body7}</div>',
        "The Idea column gives up the 80 px and still fits a 50-character title. A longer reason is cut with … and shows in full on hover.", 1144)}
  <div class="row g3 t-sm"><span class="t-xs w6 muted" style="width:60px">Phone</span><span>No change: a phone has no list view (P-02 is cards).</span><span class="muted">Its cards already show the reason after the status (S-gaps-01), cut with … when the card is narrow.</span></div></div>'''

# ---------- 8. The Move menu ----------
stubs = "".join(f'<div style="width:212px;flex:none">{media(f, 212, 200, tag=False)}</div>' for f in ("cl1", "px1", "zd1", "px2"))
ghost = '<div style="position:absolute;left:640px;top:24px;width:210px;height:250px;border:1.5px dashed var(--border-strong);border-radius:8px;display:flex;align-items:flex-end;justify-content:center;padding-bottom:8px"><span class="t-xs muted">where S1-07 drew it</span></div>'
crop8 = f'''<div style="position:relative;width:880px;height:440px;background:var(--bg);border:1px solid var(--border);border-radius:8px;overflow:hidden">
  <div class="row g4" style="padding:24px;opacity:.55">{stubs}</div>{ghost}
  <div style="position:absolute;left:0;right:0;bottom:24px;display:flex;justify-content:center">{selbar(3, menu=move_menu(3, "left:0;bottom:calc(100% + 18px);width:240px"))}</div></div>'''
g8 = f'''<div class="row g5 start">{side("Desktop · S1-07, three cards ticked", crop8, w=880)}
  {side("Phone", '<div class="col g2 t-sm" style="width:300px;margin-top:4px"><span>The same list, from the same button: see 12.</span><span class="muted">Order: the folders in the rail tree’s own order, nested as the tree has them (Hangovers and Gut science inside Dr. Pickle rants), without the folder you’re in. Unsorted and New folder… come last.</span></div>')}</div>'''

# ---------- 12. Selecting several on a phone ----------
pa = phone(FTOP(), PTABS + pcards(IDEAS[:4], ["on", "on", "off", "off"]), tabs=selbar(2, phone_=True), h=640)
pb = phone(FTOP(), PTABS + pcards(IDEAS[:4], ["on", "on", "off", "off"]),
           tabs=selbar(2, phone_=True, menu=move_menu(2, "left:0;bottom:calc(100% + 16px);width:260px", tall=True)), h=640)
desk12 = f'<div style="padding:18px;background:var(--bg);border:1px solid var(--border);border-radius:8px">{selbar(3)}</div>'
g12 = f'''<div class="row g6 start">
  {side("Desktop · S1-07 (unchanged)", desk12, "The same bar and the same Move list as on a phone.", 400)}
  {side("Phone · press and hold a card", pa, "Ticks show on every card, as on desktop (S-gaps-02 G4). Tap to add or remove. The bar takes the tabs’ place; × or Back clears it.", 390)}
  {side("Phone · Move to…", pb, "The same list as desktop, in taller rows for a thumb. Move and Archive both come with Undo.", 390)}</div>'''

# ---------- 14. Empty Unsorted, and the phone's empty-folder line ----------
tree14 = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "folder", "UGC testimonials", {"cnt": "9"}),
          (0, "folder", "Black Friday", {"cnt": "3"}), (0, "unsorted", "Unsorted", {"cnt": "0", "on": True})]
empty3 = lambda w, h: "".join(empty_media(w, h) for _ in range(3))
LINE = "New ideas land here until you put them in a folder."
main14 = f'''<main class="main"><div class="ptop" style="height:56px"><div class="crumb">Resilia {ic("chevron-right","s12")} <b>Unsorted</b></div><span class="t-sm muted">Empty</span><span class="grow"></span>{btn("New video", "lg", "plus")}</div>
  <div class="col center g3" style="flex:1;text-align:center;padding-bottom:40px"><div class="row g2" style="opacity:.9">{empty3(72, 128)}</div>
  <span class="t-xl">Nothing in Unsorted</span><span class="t-md muted" style="max-width:380px">{LINE}</span>{btn("New video", "primary lg", "plus")}</div></main>'''
desk14 = f'<div class="screen" style="width:840px;height:560px;display:flex;border:1px solid var(--border);border-radius:8px">{rail(tree=tree14)}{main14}</div>'
pbody14 = f'''<div class="col center g3" style="flex:1;text-align:center;padding:0 28px"><div class="row g2" style="opacity:.9">{empty3(56, 100)}</div>
  <span class="t-xl">Nothing in Unsorted</span><span class="t-md muted">{LINE}</span>{btn("New video", "primary lg", "plus")}</div>'''
p14 = phone(ptop(BACK, "Unsorted", SEARCH, "Resilia · empty"), pbody14, h=560)
lines = f'''<div class="col g2 t-sm" style="width:1290px;margin-top:4px;padding:12px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
  <span class="t-xs w6 muted">An ordinary empty folder (S1-03, Black Friday): the line under “Nothing in Black Friday yet”</span>
  <div class="row g3"><span class="t-xs muted" style="width:120px">Desktop · S1-03</span><span>Start a video here, or drag ideas in from another folder in the list on the left.</span></div>
  <div class="row g3"><span class="t-xs muted" style="width:120px">Phone</span><span>Start a video here, or move ideas in from another folder.</span><span class="t-xs muted">A phone has no list on the left and can’t drag; ideas move in with Move to… (12) or the video’s own ⋯.</span></div></div>'''
g14 = f'''<div class="col g4"><div class="row g6 start">
  {side("Desktop · Unsorted with nothing in it", desk14, "No ⋯: Unsorted’s menu only holds Archived ideas (S-gaps-02), hidden at 0. No “New folder inside”: Unsorted can’t hold folders.", 840)}
  {side("Phone · the same", p14, w=390)}</div>{lines}</div>'''

# ---------- 19. The phone folder's ⋯ ----------
def mi(i, t, cls="", tall=True, right=""):
    s = ' style="height:40px;font-size:14px"' if tall else ""
    return f'<div class="mi{cls}"{s}>{ic(i,"s14")}{t}{right}</div>'


ARCH2 = '<span class="grow"></span><span class="t-xs muted">2</span>'
fmenu = lambda tall: (mi("folder-plus", "New folder inside", tall=tall) + mi("pencil", "Rename", tall=tall) + mi("arrow-right-left", "Move to…", tall=tall)
                      + mi("trash", "Delete folder…", " bad-t", tall=tall) + '<div class="sepm"></div>' + mi("archive", "Archived ideas", tall=tall, right=ARCH2))
head19 = f'''<div class="row g2" style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 12px;width:440px">
  <div class="crumb">Resilia {ic("chevron-right","s12")} <b>Week of 3 Nov</b></div><span class="grow"></span><span class="iconbtn b">{ic("ellipsis","s14")}</span>{btn("New video", "primary", "plus")}</div>
  <div class="menu" style="position:static;width:230px;margin:6px 0 0 108px">{fmenu(False)}</div>'''
p19 = phone(FTOP(SEARCH + MORE_ON), PTABS + pcards(IDEAS[:4]) + f'<div class="menu" style="right:8px;top:4px;width:250px;z-index:10">{fmenu(True)}</div>', h=640)
uns19 = f'''<div class="col g2" style="width:250px"><div class="menu" style="position:static;width:250px">{mi("archive", "Archived ideas", tall=True, right='<span class="grow"></span><span class="t-xs muted">1</span>')}</div>
  <span class="t-xs muted">On Unsorted the menu holds only Archived ideas, as on desktop. With none archived there’s no ⋯, just search.</span>
  <span class="t-xs muted" style="margin-top:8px">Rename turns the name in the top bar into a text box. Move to… opens the folder list from 8. Delete folder… asks first, then Undo, as on desktop (S0-01).</span></div>'''
g19 = f'''<div class="row g6 start">
  {side("Desktop · S-gaps-02 G1 + G2 (approved, unchanged)", head19, w=440)}
  {side("Phone · P-02 with ⋯ beside search", p19, w=390)}
  {side("Phone · on Unsorted", uns19, w=250)}</div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 6: the open folder</span><span class="t-sm muted" style="max-width:1100px">Five questions from the brand-home build (#1304, 4 Nov), drawn at full size: desktop (1440) and phone (390) side by side. Where an approved board already settles a point, it says so and is drawn as that board has it. Everything else is one recommended option, for Reed’s yes or no. The boards they extend are unchanged until Reed answers.</span></div>
  <div class="col g8" style="row-gap:40px">
  {cell(7, "The list view’s Status column (S1-05)", "S1-05 draws it 150 px wide. S-gaps-01 puts the reason after the status, which needs about 230 px. The build uses 230 px.", g7,
        [("ok", "Already specified by S-gaps-01", "the list shows the reason after the status, like the cards and the header."),
         (*ASK, "Status is 230 px wide, taken from the Idea column. Why: at 150 px “Needs a fix · Stopped at clip 4” is cut off before the reason, and the reason is the part you act on.")])}
  {cell(8, "Where the Move menu opens, and its order (S1-07)", "S1-07 draws the menu off to the right, over the cards. The build puts it above the bar’s right end, in the tree’s order.", g8,
        [("ok", "Already specified by S1-07", "the order: the menu lists the folders exactly as the rail’s tree does, without the folder you’re in; Unsorted and New folder… come last."),
         (*ASK, "The menu opens straight up from the Move to… button, its left edge on the button. Why: a menu belongs to the button you pressed; S1-07’s spot floats free of the bar.")])}
  {cell(12, "Selecting several ideas on a phone", "S1-07 is a desktop board. The build lets only desktop select.", g12,
        [(*ASK, "Phones select too: press and hold a card, then tap more; the dark bar replaces the tabs, with the same Move to… and Archive. Why: a phone can’t drag ideas onto the tree, so without it, tidying a folder means opening every video.")])}
  {cell(14, "Empty Unsorted’s words, and the phone’s empty-folder line", "No board draws an empty Unsorted, and S1-03’s line points at “the list on the left”, which a phone doesn’t have.", g14,
        [(*ASK, "Unsorted says “Nothing in Unsorted · New ideas land here until you put them in a folder.” with New video; a phone’s empty folder says “move ideas in from another folder.” Why: you can’t drag into Unsorted, and a phone has no list on the left.")])}
  {cell(19, "The ⋯ on a phone folder (P-02)", "P-02 draws only search. Without a ⋯ a phone can’t rename, move or delete a folder, or reach Archived ideas.", g19,
        [("ok", "Already specified by S-gaps-02", "what’s in the menu: New folder inside, Rename, Move to…, Delete folder…, then Archived ideas · N (hidden at 0)."),
         (*ASK, "A ⋯ beside search in P-02’s top bar, opening that same menu under it. Why: it’s the only way to reach those on a phone, and the video page already does the same (S-gaps-03).")])}
  </div>'''

board("S-gaps-06", "Gaps the builders found, part 6", "5 options for Reed: list Status width, Move menu, phone selecting, empty Unsorted, phone folder ⋯", sheet, "s", h=4120)
