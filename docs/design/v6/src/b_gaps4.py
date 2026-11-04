"""S-gaps-04: more states the boards don't draw (the folder-tree builder, 4 Nov). For Reed's yes or no."""
from lib import *

W = 640


def cell(n, title, ask, drawn, note):
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="row g2 t-sm start"><span class="tag ok" style="flex:none">Approved by Reed, 4 Nov</span><span class="muted">{note}</span></div></div>'''


def rail_box(r, h=640):
    return f'<div class="screen" style="width:248px;height:{h}px;display:flex;border:1px solid var(--border);border-radius:8px;flex:none">{r}</div>'


SHORT = [(0, "folder", "Week of 3 Nov", {"cnt": "10"}), (0, "folder", "Dr. Pickle rants", {"cnt": "124"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
SCRIPTS = f'<div class="rhead">Library</div><div class="ritem on">{ic("file-text","s14")}Scripts</div>'

# R1: Scripts first under Library
r1 = rail(tree=SHORT, active=None).replace('<div class="rhead">Library</div>', SCRIPTS, 1)
g1 = f'''<div class="row g5 start">{rail_box(r1)}<div class="col g2 t-sm" style="width:300px;margin-top:8px"><span>Scripts stays as v5 draws it (the table, a script’s Overview, the writing steps). It just gets a row in the rail.</span>
  <span class="muted">Library order: Scripts, Cast &amp; places, Media, Brand kit.</span></div></div>'''

# R2: quick search under the magnifier
res = [("idea", "Bloated after pizza", "need", "Week of 3 Nov"), ("idea", "Pizza night regrets", "ok", "UGC testimonials"), ("idea", "Caught with the pizza boxes", "need", "UGC testimonials"), ("folder", "Pizza promos", None, "folder · 4 ideas")]
rl = "".join(f'<div class="mi{" on" if i == 0 else ""}">{f'<span class="dot {d}" style="margin:0 4px"></span>' if k == "idea" else ic("folder","s14")}<span class="grow ell">{t}</span><span class="t-xs muted">{w}</span></div>' for i, (k, t, d, w) in enumerate(res))
g2 = f'''<div style="position:relative;height:270px;background:#f6f6f8;border:1px solid var(--border);border-radius:8px;padding:10px 8px;width:420px">
  <div class="row g2"><span class="btn grow" style="justify-content:flex-start">{ic("plus","s14")}New video</span><span class="iconbtn b" style="background:var(--surface-3)">{ic("search","s14")}</span></div>
  <div class="menu" style="left:8px;top:52px;width:400px"><div class="input" style="height:32px;margin:2px 2px 6px;color:var(--text);border-color:var(--accent)">{ic("search","s14")}pizza</div>{rl}
  <div class="sepm"></div><div class="mi"><span class="t-xs muted">Enter opens the first · ↑↓ to move · Esc closes</span></div></div></div>
  <span class="t-xs muted" style="display:block;margin-top:8px">Searches this brand’s idea titles and folder names. Picking one opens it. Each idea shows its status dot and its folder.</span>'''

# R3: the phone's Library and More tabs; an editor's tabs
def phone_mini(title, rows, tabs_on, editor=False):
    rr = "".join(f'<div class="row g3" style="height:40px;padding:0 12px;border-bottom:1px solid var(--border);font-size:13px">{ic(i,"s14 muted")}<span class="grow">{t}</span>{f"<span class=badge style=background:var(--warning-soft);color:var(--warning)>{b}</span>" if b else ""}{ic("chevron-right","s12 muted")}</div>' if t != "-" else '<div style="height:8px;background:var(--surface-2)"></div>' for i, t, b in rows)
    tabs = [("film", "Videos"), ("users", "Library"), ("clock" if editor else "inbox", "My requests" if editor else "Needs you"), ("ellipsis", "More")]
    tb = "".join(f'<span style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;font-size:9px;white-space:nowrap;color:{"var(--text)" if n == tabs_on else "var(--text-muted)"}">{ic(i,"s14")}{n}</span>' for i, n in tabs)
    return f'''<div style="width:190px;height:350px;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--surface);display:flex;flex-direction:column;flex:none">
      <div style="padding:10px 12px;border-bottom:1px solid var(--border)" class="t-sm w6">{title}</div><div style="flex:1">{rr}</div>
      <div class="row" style="border-top:1px solid var(--border);padding:6px 0 8px">{tb}</div></div>'''


lib_rows = [("file-text", "Scripts", None), ("users", "Cast & places", None), ("image", "Media", None), ("palette", "Brand kit", None)]
more_rows = [("clapperboard", "In production", None), ("chart-column", "Usage", None), ("users", "Team", None), ("settings", "Settings", None), ("-", "-", None), ("user-round", "Your account", None), ("arrow-left", "Sign out", None)]
ed_rows = [("clock", "Gut check: start", None), ("clock", "Why IPAs: 2 redos", None), ("clock", "Pizza boxes: looks", None)]
g3 = f'''<div class="row g3 start">{phone_mini("Library", lib_rows, "Library")}{phone_mini("More", more_rows, "More")}{phone_mini("My requests", ed_rows, "My requests", editor=True)}</div>
  <span class="t-xs muted" style="display:block;margin-top:8px">Library and More are short lists that open the same pages as desktop. An editor’s third tab is My requests instead of Needs you, and More has no Studio rows.</span>'''

# R4: My requests (editor)
reqs = [("sk2", "Gut check", "Start the video", "up to 164 credits", "Sent 11:26"), ("drp_3", "Why IPAs hit harder", "Redo clips 9 and 12, past the budget", "up to 20 credits", "Sent 10:31"),
        ("skit_2", "Caught with the pizza boxes", "3 generated looks for the husband", "up to 3 credits", "Sent 11:40")]
rq = "".join(f'<div class="lrow" style="padding:10px 12px">{media(i,30,53,tag=False)}<div class="col grow"><span class="t-sm w6">{v}</span><span class="t-xs muted">{w} · {c}</span></div><span class="t-xs muted" style="width:70px">{s}</span>{status("wait","Waiting")}{btn("Withdraw")}</div>' for i, v, w, c, s in reqs)
done = "".join(f'<div class="lrow" style="padding:8px 12px"><span class="t-sm grow">{v} · <span class="muted">{w}</span></span>{st}</div>' for v, w, st in [("3 signs your gut is angry", "start the video", status("ok", "Approved")), ("Night-time bloat", "2 extra takes", status("bad", "Declined"))])
g4 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px" class="col g3">
  <div class="row g2"><span class="t-xl">My requests</span><span class="badge n">3</span></div>
  <span class="t-sm muted">Presses waiting for the owner’s OK. Nothing is charged while they wait. Withdraw cancels one.</span>
  <div class="list">{rq}</div><span class="t-xs w6 muted">Answered this week</span><div class="list">{done}</div></div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 4</span><span class="t-sm muted">Four states the boards don’t draw (the folder-tree builder, 4 Nov). Reed approved all of them on 4 Nov (“yes to all”). The boards they extend are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell("R1", "Scripts in the rail", "S0-01’s rail has no Scripts row, but v6 keeps Scripts.", g1, "“Scripts” first under Library: Scripts, Cast & places, Media, Brand kit.")}
  {cell("R2", "The magnifier beside New video", "Builder’s proposal.", g2, "A quick search over this brand’s idea titles and folder names; results in a list under the button; picking one opens it.")}
  {cell("R3", "The phone’s Library and More tabs (P-01)", "Builder’s proposal.", g3, "Library = Scripts, Cast & places, Media, Brand kit. More = the Studio rows plus the account items. An editor’s third tab is My requests.")}
  {cell("R4", "My requests (an editor)", "Builder’s proposal.", g4, "A small page listing the editor’s presses waiting for the owner, each with Withdraw, and this week’s answers. Credits only.")}
  </div>'''

board("S-gaps-04", "Gaps the builders found, part 4", "Approved: Scripts in the rail, quick search, phone Library and More, My requests", sheet, "s", h=1460)
