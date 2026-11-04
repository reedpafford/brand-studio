"""S-gaps-08: three Clips-tab details the boards leave open (the Clips builder, screen 8, 4 Nov). For Reed's yes or no."""
from lib import *
from b_s56 import clip_row
from b_phone import ptop, BACK, vtop

W = 1344
BACKC = f'<span class="row g1 accent-t w5" style="font-size:14px;padding-right:6px">{ic("chevron-left","s20")}Clips</span>'
EX = '<span class="tag n" style="flex:none">Prices are examples</span>'


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


def phone(top, body, h=700):
    """A 390 phone at 1x, cut off at h. (class order "p screen" keeps render.py from treating the sheet as a phone board.)"""
    return f'''<div class="p screen" style="height:{h}px;border:1px solid var(--border);border-radius:14px;flex:none">{phone_status()}{top}
      <div class="pbody">{body}</div><div class="home-ind"><i></i></div></div>'''


def desk_panel(body, h, clips="6", cast="1", w=792):
    tabs = [("Cut", None), ("Clips", clips), ("Cast", cast), ("Plan", None), ("Script", None)]
    return f'<div style="width:{w}px;height:{h}px;display:flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;flex:none">{panel("Clips", body, tabs)}</div>'


def box(inner, w, pad="14px 16px"):
    return f'<div class="col g3" style="width:{w}px;padding:{pad};background:var(--surface);border:1px solid var(--border);border-radius:8px;flex:none">{inner}</div>'


# ---------- 1. Grid or list ----------
IMGS = ["ugc_1", "ugcb_4", "ug1", "ugc_3", "ug2", "ugc_5"]
TITLES = ["Mark to camera: “Pizza night used to wreck me”", "On the couch, holding his belly", "Coffee, again", "Mark: “Then I tried this”", "The capsule, close", "Mark: “Link in my bio”"]
DURS = ["6 s", "4 s", "3 s", "7 s", "3 s", "5 s"]
STS = [("ok", "In the cut")] * 2 + [("ok", "Redone")] + [("ok", "In the cut")] * 3

grid = "".join(f'<div class="col g2" style="width:150px">{media(i,150,266,play=True,dur=d)}<div class="row g2"><span class="t-sm w6">Clip {n+1}</span><span class="grow"></span>{status(*s)}</div><span class="t-xs muted">{t}</span></div>'
               for n, (i, t, s, d) in enumerate(zip(IMGS, TITLES, STS, DURS)))
bodyG = f'<div class="row between"><span class="t-lg">Clips</span><span class="t-sm muted">6 clips · 28 s · all in the cut</span></div><div class="row g4 wrap start">{grid}</div>'
deskG = desk_panel(bodyG, 470)

groups = [("Scene 1 · Hook", [0, 1]), ("Scene 2 · Pizza nights", [2]), ("Scene 3 · The fix", [3, 4, 5])]
lrows = []
for g, idx in groups:
    lrows.append(f'<div class="lrow hd" style="padding:8px 10px">{ic("chevron-down","s12")}<span class="w6" style="color:var(--text)">{g}</span><span class="grow"></span><span>{len(idx)}</span></div>')
    for i in idx:
        lrows.append(clip_row(i + 1, IMGS[i], TITLES[i], DURS[i], "UGC" if i in (0, 3, 5) else "Seedance 2.0", status(*STS[i]), sel=(i == 2)))
detail3 = f'''<div class="col g3"><div class="row g2"><span class="t-lg">Clip 3</span><span class="t-sm muted">Scene 2 · 3 s · B-roll</span><span class="grow"></span>{status("ok","Redone")}</div>
  <div class="row g2 start t-sm" style="padding:10px 12px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px">{ic("eye","s14")}<span><b class="w6">Found:</b> the coffee pour froze for half a second. <b class="w6">Did:</b> remade it.</span></div>
  <div class="row g3 start"><div class="take best" style="width:120px">{media("ug1",120,213,play=True,dur="3 s",tag=False)}<span class="t-sm w6">Take 2 · in the cut</span></div></div>
  <span class="t-xs muted">Model, why, words, prompt and the presses as on S6-02</span></div>'''
bodyL = f'''<div class="row g3"><span class="btn ghost" style="padding:0 4px">{ic("arrow-left","s14")}All clips</span><span class="grow"></span><span class="t-sm muted">6 clips · grouped by scene</span></div>
  <div class="row g4 start"><div class="list" style="width:300px;flex:none">{"".join(lrows)}</div><div class="grow">{detail3}</div></div>'''
deskL = desk_panel(bodyL, 560)

PTOP = vtop("Bloated after pizza", status("ok", "Delivered"), on="Preview").replace("up to $16.86", "$4.80 of up to $7.40")
PSEG = '<div class="seg" style="flex:none"><span>Cut</span><span class="on">Clips</span><span>Cast</span><span>Plan</span><span>Script</span></div>'
pgrid = "".join(f'<div class="col g1">{media(i,175,311,play=True,dur=d)}<div class="row g2"><span class="t-sm w6">Clip {n+1}</span><span class="grow"></span>{status(*s)}</div></div>' for n, (i, s, d) in enumerate(zip(IMGS[:4], STS, DURS)))
pG = phone(PTOP, f'<div class="col g2" style="padding:12px 14px">{PSEG}<span class="t-xs muted" style="margin-top:4px">6 clips · 28 s · all in the cut</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:14px 12px;padding:0 14px;flex:none">{pgrid}</div>', h=610)
pO = phone(ptop(BACKC, "Clip 3", "", "Scene 2 · 3 s · Seedance 2.0"),
           f'''<div class="col g3" style="padding:14px"><div class="row g2 start t-sm" style="padding:10px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px">{ic("eye","s14")}<span><b class="w6">Found:</b> the pour froze. <b class="w6">Did:</b> remade it.</span></div>
             <div class="row g3">{media("ug1",170,302,play=True,cls="sel")}</div><span class="t-xs muted">Take 2 · in the cut</span>
             <div class="col g2">{btn("Change this…","lg","pencil","$0.24")}{btn("Another take","lg","refresh-cw","$0.24")}</div></div>''', h=610)
g1 = f'''<div class="row g6 start">
  <div class="col g4">{side("Desktop · 12 clips or fewer: S6-01’s grid", deskG, w=792)}{side("Desktop · press a card: S6-02’s list, that clip open", deskL, "“All clips” goes back to the grid. Over 12 clips there’s no grid: S6-02 and S6-04’s grouped list, as drawn.", 792)}</div>
  <div class="col g4">{side("Phone · 12 or fewer: two across", pG, w=390)}{side("Phone · tap a clip: P-11", pO, "“‹ Clips” at the top left goes back to the grid, a clear way back (Reed). Over 12: P-10’s grouped list, as drawn.", 390)}</div></div>'''

# ---------- 2. Stills in an open clip ----------
def tile(img, label, sub, w=100, h=178, play=False, cls="", faded=False, press=""):
    m = media(img, w, h, play=play, dur="4 s" if play else None, tag=False, cls=cls)
    if not play:
        m = m.replace('</div>', f'<span class="tag n" style="position:absolute;left:6px;top:6px">{ic("image","s12")}Still</span></div>', 1)
    p = f'<span class="t-xs accent-t w5">{press}</span>' if press else ""
    return f'<div class="col g1" style="width:{w}px;{"opacity:.7" if faded else ""}">{m}<span class="t-sm w6">{label}</span><span class="t-xs muted">{sub}</span>{p}</div>'


row2 = (tile("pk1", "Still · in use", "Made 10:12") + tile("pk1pv", "Still 1", "Replaced 10:12", faded=True, press="Use this still · free: reuses Take 1")
        + '<div style="width:1px;align-self:stretch;background:var(--border)"></div>'
        + tile("pk1pv", "Take 1", "Dropped: eyes on the stomach", play=True) + tile("pk1", "Take 2 · in the cut", "From still 2", play=True, cls="sel"))
detail2 = f'''<div class="row g2"><span class="t-lg">Clip 7</span><span class="t-sm muted">Scene 2 · What beer does · 4 s · B-roll</span><span class="grow"></span>{status("ok","In the cut")}</div>
  <div class="row g3 start">{row2}</div>
  <div class="row g2 wrap">{btn("Change the still…", "", "image", "$0.36")}<span class="t-xs muted">a new still and a new take</span></div>
  <div class="kv" style="grid-template-columns:96px 1fr"><span class="k">Model</span><span>Seedance 2.0 · 480p</span><span class="k">Still</span><span>Nano Banana 2.1</span><span class="k">Cost</span><span>$0.71 (2 stills, 2 takes)</span></div>
  <div class="row g2 wrap">{btn("Change this…", "", "pencil", "$0.32")}{btn("Another take", "", "refresh-cw", "$0.32")}{btn("Add sound effects", "", "volume-2", "$0.01")}</div>'''
desk2 = box(detail2, 500)
prow = (tile("pk1", "Still · in use", "10:12", 110, 196) + tile("pk1pv", "Still 1", "Replaced", 110, 196, faded=True, press="Use · free: reuses Take 1")
        + tile("pk1pv", "Take 1", "Dropped", 110, 196, play=True) + tile("pk1", "Take 2 · in the cut", "", 110, 196, play=True, cls="sel"))
p2 = phone(ptop(BACKC, "Clip 7", "", "Scene 2 · 4 s · Seedance 2.0"),
           f'''<div class="col g3" style="padding:14px"><div class="row g3 start" style="overflow:hidden;flex-wrap:nowrap">{prow}</div><span class="t-xs muted">The row scrolls sideways: stills first, then takes.</span>
             <div class="col g2">{btn("Change the still…","lg","image","$0.36")}{btn("Change this…","lg","pencil","$0.32")}{btn("Another take","lg","refresh-cw","$0.32")}</div></div>''', h=640)
why2 = box('''<span class="t-xs w6 muted">How it works</span>
  <span class="t-sm">The still the take was made from sits first in the takes row. Earlier stills sit after it, faded, so nothing is lost.</span>
  <span class="t-sm muted">Changing a still needs a new take once the clip is made, so its price covers both. Before the take is made it’s one picture.</span>
  <span class="t-sm muted">“Use this still” reuses a take already made from that still when there is one (free, here Take 1). Only otherwise does it make a new take, with its price.</span>
  <span class="t-sm muted">Every price is the real “up to” for the model, the length and the work, never a fixed figure. Editors see credits.</span>
  <span class="t-sm muted">No per-still approval list. It doesn’t replace the Cast &amp; places approval: a still change that would alter an approved character or place goes back to Cast instead.</span>''', 300)
g2 = f'''<div class="row g6 start">
  {side("Desktop · S6-02’s open clip, stills first in the row " + EX, desk2, w=500)}
  {side("Phone · P-11, the same row", p2, w=390)}
  {why2}</div>'''

# ---------- 5. Use this take ----------
def takes(before=True, w=150, h=266):
    t1 = f'<div class="take{"" if before else " best"}" style="width:{w}px">{media("pk1pv",w,h,play=True,dur="4 s",tag=False)}<span class="t-sm w6">Take 1{"" if before else " · in the cut"}</span><span class="t-xs muted">{"Dropped: the eyes landed on the stomach" if before else "Picked by Reed · 10:31"}</span>{btn("Use this take", "", None, "free") if before else ""}</div>'
    t2 = f'<div class="take{" best" if before else ""}" style="width:{w}px">{media("pk1",w,h,play=True,dur="4 s",tag=False)}<span class="t-sm w6">Take 2{" · in the cut" if before else ""}</span><span class="t-xs muted">{"Remade on Seedance 2.0" if before else "Not used"}</span>{"" if before else btn("Use this take", "", None, "free")}</div>'
    return f'<div class="row g3 start">{t1}{t2}</div>'


after_bar = f'<div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("loader-circle","s14 accent-t")}<span>Making Cut 3 with your change · free · about 40 s. Cut 2 keeps playing until then.</span></div>'
desk5 = f'''<div class="row g5 start">{box(f'<span class="t-xs w6 muted">Before: S6-02’s takes</span>{takes(True)}', 360)}
  {box(f'<span class="t-xs w6 muted">After “Use this take”</span>{takes(False)}{after_bar}', 380)}</div>'''
p5 = phone(ptop(BACKC, "Clip 7", "", "Scene 2 · 4 s · Seedance 2.0"),
           f'''<div class="col g3" style="padding:14px"><div class="row g3 start">{takes(True, 170, 302).replace('class="row g3 start"', 'class="row g3 start" style="flex-wrap:nowrap"')}</div>
             <div class="col g2">{btn("Change this…","lg","pencil","$0.32")}{btn("Another take","lg","refresh-cw","$0.32")}</div></div>''', h=640)
g5 = f'''<div class="row g6 start">
  {side("Desktop · the open clip (S6-02)", desk5, "The cut is rebuilt by itself, free, and the previous cut plays until the new one is ready. Any paid review of it follows the budget and approval rules. The cut editor already swaps takes this way (S7-05).", 780)}
  {side("Phone · P-11", p5, w=390)}</div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 8: the Clips tab</span><span class="t-sm muted" style="max-width:1100px">Three questions from the Clips builder (screen 8, 4 Nov), drawn at full size: desktop (1440) and phone (390) side by side. Reed approved all three on 4 Nov, with the notes under each. They are part of v6, and the boards they extend are unchanged. Prices drawn are examples: the app shows the real “up to” for the model, the length and the work, and editors see credits.</span></div>
  <div class="col g8" style="row-gap:40px">
  {cell(1, "Grid or list: when each shows", "S6-01 draws a grid, S6-02 and S6-04 a grouped list; none says when. Builder’s proposal: 12 clips or fewer opens as the grid; over 12, always the list.", g1,
        [("ok", "Already specified by S6-01, S6-02, S6-04, P-10 and P-11", "a short video is a grid (6 clips); 24 and 118 clips are the list grouped by scene with one clip open; a phone opens one clip full screen."),
         ("ok", "Approved by Reed, 4 Nov", "12 clips or fewer: the grid; pressing a card opens the list with that clip open, and “All clips” goes back. Over 12: the list grouped by scene. Phone: two columns, with a clear way back (“‹ Clips”).")])}
  {cell(2, "Stills in an open clip", "Today’s Clips tab also holds the storyboard stills (draw, change, versions, approve). S6 draws none of it. Builder’s proposal: the still first in the takes row, “Still · in use”, with Change this…; versions and Approve dropped.", g2,
        [("ok", "Already specified by rules 21 and 24", "no Approve on stills (the director approves clean work), and “Change this…” is how a still is changed, with the price first."),
         ("ok", "Approved by Reed, 4 Nov", "Earlier stills stay reachable in the same row, with no per-still approval list. Each press says whether it needs a new take, with the real “up to” price (credits for editors). A suitable existing take is reused. A change that would alter an approved character or place goes back to Cast.")])}
  {cell(5, "Picking a take", "S6-02 shows “Take 1 · dropped” and “Take 2 · in the cut” but no press to swap. Builder’s proposal: “Use this take” (free); the cut goes out of date until it’s remade.", g5,
        [("ok", "Already specified by S7-05", "a change to the cut makes the next cut by itself, free, about 40 s, and the current cut keeps playing until then."),
         ("ok", "Approved by Reed, 4 Nov", "“Use this take · free”. The cut is rebuilt by itself and the previous cut stays playable until it’s ready. Any paid review follows the budget and approval rules.")])}
  </div>'''

board("S-gaps-08", "Gaps the builders found, part 8", "Approved: grid or list, earlier stills, Use this take", sheet, "s", h=3400)
