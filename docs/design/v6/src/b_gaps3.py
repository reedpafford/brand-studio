"""S-gaps-03: more states the boards don't draw (the video-page builder, 4 Nov). For Reed's yes or no."""
from lib import *

W = 640


def cell(n, title, ask, drawn, note):
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="row g2 t-sm start"><span class="tag ok" style="flex:none">Approved by Reed, 4 Nov</span><span class="muted">{note}</span></div></div>'''


def switch(on, dis=False):
    bg = "var(--accent)" if on else ("var(--surface-3)" if not dis else "var(--surface-2)")
    return f'<span style="width:30px;height:18px;border-radius:9px;background:{bg};position:relative;flex:none;{"opacity:.5" if dis else ""}"><i style="position:absolute;top:2px;{"right" if on else "left"}:2px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 1px 2px rgb(0 0 0 / .2)"></i></span>'


# 1. Locks +N opened
chips = "".join([chip("Presenter · Dr. Pickle", None, "lock", "lockd"), chip("Dr. Pickle", "Cast", "lock", "lockd"), chip("about 60 s", "Length"), chip("Locks +1", None, "sliders-horizontal", "on")])
rows = [("Cast", "Dr. Pickle", True, False), ("Style", "Dr. Pickle", True, False), ("Length", "about 60 s", False, False),
        ("Song", "not in a Presenter video", False, True), ("End line", "“Link in my bio.”", True, False)]
lr = "".join(f'<div class="row g3" style="padding:7px 10px"><span class="t-sm w5" style="width:70px">{n}</span><span class="t-sm muted grow ell">{v}</span>{switch(on, dis)}</div>' for n, v, on, dis in rows)
lr += f'<div class="row g3" style="padding:7px 10px;border-top:1px solid var(--border)"><span class="t-sm w5" style="width:70px">Screens</span><span class="t-sm muted grow">3 · picked in the plan</span>{ic("lock","s14 muted")}</div>'
g1 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px" class="col g2">
  <div class="row g3"><span class="t-lg">Beer gut doctor rant</span>{status("work","Working")}</div><div class="locks">{chips}</div></div>
  <div class="menu" style="position:static;width:340px;margin:6px 0 0 296px;padding:4px 0">
    <div class="row" style="padding:4px 10px 6px"><span class="t-xs w6 muted">Locks</span><span class="grow"></span><span class="t-xs muted">one press each</span></div>{lr}</div>
  <span class="t-xs muted" style="display:block;margin-top:8px">The first chips are labels: a lock icon means that choice is locked. “+1” counts locks that are on and aren’t already shown as a chip (here: End line). A locked choice is used as is; the director builds around it.</span>'''

# 2. The video's ⋯ menu
def vmenu(items):
    return '<div class="menu" style="position:static;width:230px">' + "".join(
        f'<div class="mi{" bad-t" if bad else ""}">{ic(i,"s14")}{t}</div>' if t != "-" else '<div class="sepm"></div>' for i, t, bad in items) + "</div>"


g2 = f'''<div class="row g6 start">
  <div class="col g2"><span class="t-xs w6 muted">While it’s being made</span>{vmenu([("folder","Move to folder…",False),("download","Download MP4 (Cut 1)",False),("-","-",False),("x","Release this version",True)])}
    <span class="t-xs muted" style="width:230px">Download shows once a cut exists.</span></div>
  <div class="col g2"><span class="t-xs w6 muted">Once it’s done</span>{vmenu([("folder","Move to folder…",False),("download","Download MP4",False),("-","-",False),("archive","Archive",False)])}
    <span class="t-xs muted" style="width:230px">Archived videos are reached from the folder’s ⋯ menu (S-gaps-02).</span></div></div>
  <span class="t-xs muted" style="display:block;margin-top:10px">Same menu on the phone, from the ⋯ in the top bar (P-04, P-05).</span>'''

# 3. The phone Preview always shows its tab row
def ptopmini(row):
    return f'''<div style="width:300px;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--surface)">
  <div class="row g2" style="padding:8px 10px;border-bottom:1px solid var(--border)">{ic("chevron-left","s14")}<div class="col grow"><span class="t-sm w6">Beer gut doctor rant</span><span class="t-xs muted">{status("ok","Delivered")}</span></div>{ic("ellipsis","s14")}</div>
  <div style="padding:6px 8px;border-bottom:1px solid var(--border)"><div class="seg" style="display:flex"><span style="flex:1;justify-content:center">Chat</span><span class="on" style="flex:1;justify-content:center">Preview</span></div></div>
  {row}<div class="row" style="justify-content:center;padding:10px">{media("drp_2", 120, 213, tag=False)}</div></div>'''


tabrow = '<div style="padding:6px 8px;overflow:hidden"><div class="seg" style="white-space:nowrap"><span class="on">Cut</span><span>Clips</span><span>Cast</span><span>Plan</span><span>Script</span></div></div>'
g3 = f'''<div class="row g5 start"><div class="col g2"><span class="t-xs w6 muted">On P-05 now <span class="tag bad">slip</span></span>{ptopmini("")}</div>
  <div class="col g2"><span class="t-xs w6 muted">Fixed: the row always shows</span>{ptopmini(tabrow)}</div></div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 3</span><span class="t-sm muted">Two states the boards don’t draw and one slip on P-05 (the video-page builder, 4 Nov). Reed approved all of them on 4 Nov (“yes to all”). The boards they extend are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell(1, "“Locks +N” opened (S3-01, S3-09)", "Builder’s proposal.", g1, "A small menu under the chip with a toggle per lock (Cast, Style, Length, Song, End line); Screens is read-only, picked in the plan. The other chips are labels.")}
  {cell(2, "The video’s ⋯ menu (S3 header, P-04, P-05)", "Builder’s proposal.", g2, "Move to folder…, Download MP4 once a cut exists, then Release this version while it’s being made, or Archive once it’s done.")}
  {cell(3, "The phone Preview’s tabs: a slip on P-05", "P-05 has no Cut/Clips/Cast/Plan/Script row, so Cast and Clips can’t be reached.", g3, "The row always shows on the phone Preview, as on P-09 and P-10.")}
  </div>'''

board("S-gaps-03", "Gaps the builders found, part 3", "Approved: Locks menu, the video’s ⋯ menu, phone Preview tabs", sheet, "s", h=1160)
