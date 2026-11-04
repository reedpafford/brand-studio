"""S-gaps-02: more states the boards don't draw (the folder builder, 3 Nov). For Reed's yes or no."""
from lib import *
from b_s01 import IDEAS

W = 640


def cell(n, title, ask, drawn, note):
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="row g2 t-sm start"><span class="tag ok" style="flex:none">Approved by Reed, 3 Nov</span><span class="muted">{note}</span></div></div>'''


def mini_card(i, w=118, h=160, box=None):
    t, f, k, s, *_ = i
    b = ""
    if box == "on":
        b = f'<span class="check on" style="position:absolute;right:6px;top:6px">{ic("check","s12")}</span>'
    elif box == "off":
        b = '<span class="check" style="position:absolute;right:6px;top:6px"></span>'
    return f'<div class="col g1" style="width:{w}px;position:relative">{media(f, w, h, tag=False, cls="sel" if box == "on" else "")}{b}<span class="t-sm w6 ell">{t}</span>{status(k, s.split(" · ")[0])}</div>'


# G1 + G2: the folder's ⋯ menu, and how Archived is reached
head = f'''<div class="row g2" style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 12px">
  <div class="crumb">Resilia {ic("chevron-right","s12")} <b>Week of 3 Nov</b></div><span class="grow"></span><span class="iconbtn b">{ic("ellipsis","s14")}</span>{btn("New video", "primary", "plus")}</div>'''
menu = f'''<div class="menu" style="position:static;width:230px;margin:6px 0 0 auto;margin-right:112px">
  <div class="mi">{ic("folder-plus","s14")}New folder inside</div><div class="mi">{ic("pencil","s14")}Rename</div><div class="mi">{ic("arrow-right-left","s14")}Move to…</div>
  <div class="mi bad-t">{ic("trash","s14")}Delete folder…</div><div class="sepm"></div><div class="mi on">{ic("archive","s14")}Archived ideas<span class="grow"></span><span class="t-xs muted">2</span></div></div>'''
unsorted = f'''<div class="row g3 start" style="margin-top:14px"><div class="col g1"><span class="t-xs w6 muted">On Unsorted</span>
  <div class="menu" style="position:static;width:230px"><div class="mi on">{ic("archive","s14")}Archived ideas<span class="grow"></span><span class="t-xs muted">1</span></div></div></div>
  <span class="t-xs muted" style="width:300px;margin-top:20px">“Archived ideas” is hidden when a folder has none. It opens the archived list (S1-06), with Back to the folder.</span></div>'''
g12 = head + menu + unsorted

# G4: when card checkboxes show
g4 = f'''<div class="row g5 start"><div class="col g2"><span class="t-xs w6 muted">Hovering one card</span><div class="row g2">{mini_card(IDEAS[3], box="off")}{mini_card(IDEAS[5])}</div></div>
  <div class="col g2"><span class="t-xs w6 muted">Once one is ticked: on every card</span><div class="row g2">{mini_card(IDEAS[3], box="on")}{mini_card(IDEAS[5], box="off")}</div></div></div>
  <span class="t-xs muted" style="display:block;margin-top:10px">List view always shows them (S1-05). Esc or the × on the selection bar clears them.</span>'''

# G5: no folder picked
from b_phone import pscreen, ptop
g5 = f'''<div class="row g5 start"><div class="col g2" style="width:330px"><span class="t-xs w6 muted">Desktop: Unsorted opens</span>
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px" class="col g2">
    <div class="ritem on" style="height:28px">{ic("inbox","s14")}Unsorted<span class="cnt">2</span></div>
    <div class="row g2">{mini_card(IDEAS[1], 96, 128)}{mini_card(IDEAS[9], 96, 128)}</div>
    <span class="t-xs muted">Also where a new brand starts, once it has an idea.</span></div></div>
  <div class="col g2"><span class="t-xs w6 muted">Phone: the folder list opens (P-01)</span>
  <div style="width:200px;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--surface)">
    {"".join(f'<div class="row g2" style="height:34px;padding:0 10px;border-bottom:1px solid var(--border);font-size:12px">{ic(i,"s14 muted")}<span class="grow">{n}</span><span class="t-xs muted">{c}</span></div>' for i, n, c in [("folder", "Week of 3 Nov", "10"), ("folder", "Dr. Pickle rants", "124"), ("folder", "UGC testimonials", "9"), ("inbox", "Unsorted", "2")])}</div></div></div>'''

# G6: when the set-up list shows
steps = [(True, "Name and colour"), (True, "Logo"), (False, "Characters"), (False, "Products"), (False, "Places"), (False, "Voices and presenters"), (True, "Tone and rules")]
rows = "".join(f'<div class="lrow" style="padding:8px 12px"><span class="check{" on" if d else ""}">{ic("check","s12") if d else ""}</span><span class="grow {"muted" if d else "w5"}">{t}</span>{"<span class=t-xs muted>done</span>" if d else btn("Add")}</div>' for d, t in steps)
g6 = f'''<div class="row g4 start"><div class="list" style="width:330px">{rows}</div>
  <div class="col g2 t-sm" style="width:240px"><span>Shows only while the brand has <b class="w6">no ideas and no folders</b>.</span><span class="muted">Each tick comes from what the brand already has: here a logo and tone notes were imported.</span><span class="muted">“Add” opens that part of the brand or library: Characters → Cast &amp; places, Products → Products, Voices → Presenters &amp; voices.</span><span class="muted">It goes away once the first idea or folder exists.</span></div></div>'''

# G7: P-02's phone tabs (a slip on the board)
g7 = f'''<div class="col g3"><div class="row g3"><span class="t-xs w6 muted" style="width:80px">On P-02</span><div class="seg"><span class="on">All</span><span>Needs you 2</span><span>Done 5</span></div><span class="tag bad">slip</span></div>
  <div class="row g3"><span class="t-xs w6 muted" style="width:80px">Fixed</span><div class="seg"><span class="on">All</span><span>Needs you 2</span><span>Working 2</span><span>Delivered 5</span></div><span class="tag ok">same as desktop</span></div>
  <span class="t-xs muted">If the four don’t fit a small phone, the row scrolls sideways. It never drops a tab.</span></div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 2</span><span class="t-sm muted">More states the boards don’t draw (the folder builder, 3 Nov), plus one slip on P-02. Reed approved all five on 3 Nov (“yes to all”). They are part of v6, and the boards they extend are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell("G1 + G2", "The folder’s ⋯ menu, and how Archived is reached (S1-04, S1-06)", "Builder’s proposal.", g12, "Folder menu = S0-01’s menu without “New video here”, then “Archived ideas · N” (hidden at 0). On Unsorted, only “Archived ideas”.")}
  {cell("G4", "When card checkboxes show (S1-07)", "Builder’s proposal.", g4, "On hover over a card, and on every card once one is ticked. List view always shows them.")}
  {cell("G5", "What opens when no folder is picked", "Builder’s proposal.", g5, "Desktop opens Unsorted; a phone opens the folder list (P-01).")}
  {cell("G6", "When “Set up Resilia” shows (S1-02)", "Builder’s proposal.", g6, "Only while the brand has no ideas and no folders; ticks come from what the brand has; “Add” goes to that part of the brand or library.")}
  {cell("G7", "Phone tabs on P-02: a slip", "P-02 says “Done” and has no Working; desktop says “Delivered”.", g7, "Use “All · Needs you · Working · Delivered”, like desktop.")}
  </div>'''

board("S-gaps-02", "Gaps the builders found, part 2", "Approved: folder menu and Archived, checkboxes, no folder picked, set-up list, phone tabs", sheet, "s", h=1500)
