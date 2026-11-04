"""S-gaps-07: the Cast tab (the Cast builder, screen 9, 4 Nov), redrawn to Reed's answers the same day:
A places alongside characters, each with its source; B one combined "Approve cast & places" check."""
from lib import *
from b_phone import vtop

W = 1344
OK = ("ok", "Approved by Reed, 4 Nov")
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


def phone(top, body, bottom="", h=844):
    """A 390 phone at 1x, cut off at h. (class order "p screen" keeps render.py from treating the sheet as a phone board.)"""
    return f'''<div class="p screen" style="height:{h}px;border:1px solid var(--border);border-radius:14px;flex:none">{phone_status()}{top}
      <div class="pbody">{body}</div>{bottom}<div class="home-ind"><i></i></div></div>'''


def desk_panel(body, h, foot=""):
    tabs = [("Cut", None), ("Clips", "9"), ("Cast", "6"), ("Plan", None), ("Script", None)]
    f = f'<div class="row g3" style="flex:none;padding:12px 20px;border-top:1px solid var(--border);background:var(--surface)">{foot}</div>' if foot else ""
    return f'<div style="width:792px;height:{h}px;display:flex;flex-direction:column;border:1px solid var(--border);border-radius:8px;overflow:hidden;flex:none"><div style="flex:1;min-height:0;display:flex">{panel("Cast", body, tabs)}</div>{f}</div>'


def box(inner, w):
    return f'<div class="col g2 t-sm" style="width:{w}px;padding:12px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;flex:none">{inner}</div>'


def bus_stop(w, h):
    """The House rain frame's top-left corner (street lamp, rain, the shelter), without Marcus in it."""
    iw = round(285 * w / 160) if w / h > 0.9 else round(285 * w / 90)
    return f'<div class="media" style="width:{w}px;height:{h}px"><img src="{src("house_marcus_rain")}" style="width:{iw}px;height:auto;max-width:none;object-fit:fill"></div>'


def pic(img, kind, phone_=False):
    w, h = ((44, 58) if kind == "char" else (64, 40)) if phone_ else ((54, 72) if kind == "char" else (96, 60))
    if img == "bus":
        return bus_stop(w, h)
    if img is None:
        return empty_media(w, h, "empty", f'<span class="play" style="color:var(--warning)">{ic("map-pin" if kind == "place" else "user-round","s14")}</span>')
    return media(img, w, h, tag=False)


def was(img):
    return f'<span class="row g1 t-xs muted">was {media(img, 18, 24, tag=False, style="opacity:.6")}</span>'


def irow(img, kind, name, sub, source, state, acts="", cls="", extra="", phone_=False):
    """One character or place: picture, name, where it’s used, where it came from, its state, its presses."""
    src_ = f'<span class="tag n" style="flex:none">{source}</span>'
    if phone_:
        a = f'<div class="row g2 wrap" style="margin-top:4px">{acts}</div>' if acts else ""
        return f'''<div class="role {cls}" style="padding:8px 10px;gap:10px;align-items:flex-start;flex:none">{pic(img, kind, True)}<div class="col g1 grow" style="min-width:0">
          <div class="row g2"><span class="w6 t-sm">{name}</span><span class="grow"></span>{state}</div><div class="row g2">{src_}{extra}</div>{a}</div></div>'''
    return f'''<div class="role {cls}" style="padding:10px 12px;gap:12px;align-items:center;flex:none">{pic(img, kind)}<div class="col g1 grow" style="min-width:0">
      <div class="row g2"><span class="w6">{name}</span><span class="t-sm muted">{sub}</span><span class="grow"></span>{state}</div>
      <div class="row g2">{src_}{extra}</div></div>{f'<div class="row g2" style="flex:none">{acts}</div>' if acts else ""}</div>'''


def head(t, n):
    return f'<div class="row between" style="margin-top:4px"><span class="t-md w6">{t}</span><span class="t-sm muted">{n}</span></div>'


READY = status("wait", "Ready to check")
APPR = status("ok", "Approved")
CHG = btn("Change…", "ghost", "message-square")
PSEG = '<div class="seg" style="flex:none"><span>Cut</span><span>Clips</span><span class="on">Cast</span><span>Plan</span><span>Script</span></div>'
PTOP = lambda st: vtop("Three dimes to a penthouse", st, on="Preview").replace("up to $16.86", "up to $19.40")

# ---------- A. Characters and places, each with its source ----------
WAYS = btn("From fomo’s library", "primary", "map-pin") + btn("Upload", "", "upload") + btn("Make one", "", "wand-sparkles", "$0.08")
rowsA = (head("Characters", "4") +
         irow("house_marcus_rain", "char", "Marcus", "Main character · 9 clips", "Made for this video", READY) +
         irow("sheet_gothgf", "char", "Jade", "Girlfriend · 3 clips", "From fomo’s library · “Goth GF” v4", READY) +
         irow("skit_2", "char", "Chase", "Rival · 4 clips", "Uploaded for this video · chase.jpg", READY) +
         irow("skit_3", "char", "Mom", "1 clip", "Made by the director in the chat · 09:06", READY) +
         head("Places", "3") +
         irow("bus", "place", "Bus stop in the rain", "4 clips", "Made for this video", READY) +
         irow("ug1", "place", "Marcus’s kitchen", "2 clips", "Uploaded for this video · kitchen.jpg", READY) +
         irow(None, "place", "The penthouse", "3 clips", "No look yet", status("need", "Needs a look"), cls="need",
              extra=WAYS))
bodyA = f'''<div class="row between"><span class="t-lg">Cast &amp; places</span><span class="t-sm muted">4 characters · 3 places</span></div><div class="col g2">{rowsA}</div>'''
deskA = desk_panel(bodyA, 880)
chatA = f'''<div class="col g3" style="width:400px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
  {m_dir("<p>Mom is in one clip, so I made her a look for this video. It’s with the others in Cast.</p>", "09:06")}
  {sysline("users", "Mom added to Cast · made by the director")}</div>'''
pbodyA = f'''<div class="col g2" style="padding:12px 14px">{PSEG}{head("Characters", "4")}
  {irow("house_marcus_rain", "char", "Marcus", "", "Made for this video", READY, phone_=True)}
  {irow("sheet_gothgf", "char", "Jade", "", "fomo’s library", READY, phone_=True)}
  {irow("skit_2", "char", "Chase", "", "Uploaded · this video", READY, phone_=True)}
  {irow("skit_3", "char", "Mom", "", "By the director · chat", READY, phone_=True)}
  {head("Places", "3")}
  {irow("bus", "place", "Bus stop in the rain", "", "Made for this video", READY, phone_=True)}
  {irow(None, "place", "The penthouse", "", "No look yet", status("need", "Needs a look"), btn("Library", "primary") + btn("Upload") + btn("Make", "", None, "$0.08"), "need", phone_=True)}</div>'''
pA = phone(PTOP(status("need", "Needs you")), pbodyA)
notesA = box('''<span class="t-xs w6 muted">How it works</span>
  <span>Characters and places sit together in the video’s Cast, each labelled with where it came from: the brand’s library, an upload, made for this video, or made by the director in the chat.</span>
  <span class="muted">Each one is picked from the library, uploaded, or made for this video only. Uploads and looks made here never go into the brand’s library by themselves.</span>
  <span class="muted">A place is the setting: a room, a street. The Plan tab still decides the scenes and what happens in them.</span>
  <span class="muted">When the director makes or suggests a look in the chat, it shows up here too, in the same list.</span>''', 400)
gA = f'''<div class="row g6 start">
  {side("Desktop · the Cast tab: characters, then places " + EX, deskA, w=792)}
  {side("Phone · P-09, the same list", pA, w=390)}</div>
  <div class="row g6 start" style="margin-top:20px">{side("In the chat: a look the director made lands in Cast", chatA, w=400)}{notesA}</div>'''

# ---------- B. One combined "Approve cast & places" ----------
APPROVE = btn("Approve cast &amp; places", "primary lg", "check")
banner1 = f'''<div class="row g2 start t-sm" style="padding:10px 12px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px;flex:none">{ic("users","s14")}
  <span><b class="w6">Check the cast and places together.</b> Storyboards and clips that use them wait until you approve. The rest of the plan carries on. Previews so far: $0.48 of the approved budget.</span></div>'''
mom_rev = f'<span class="tag new" style="flex:none">Revised 09:21 after your note</span>{was("skit_3")}'
rowsB1 = (head("Characters", "4") +
          irow("house_marcus_rain", "char", "Marcus", "Main character · 9 clips", "Made for this video", READY, CHG) +
          irow("sheet_gothgf", "char", "Jade", "Girlfriend · 3 clips", "From fomo’s library", READY, CHG) +
          irow("skit_2", "char", "Chase", "Rival · 4 clips", "Uploaded for this video", READY, CHG) +
          irow("skit_1", "char", "Mom", "1 clip", "Made by the director", READY, CHG, extra=mom_rev) +
          head("Places", "2") +
          irow("bus", "place", "Bus stop in the rain", "4 clips", "Made for this video", READY, CHG) +
          irow("ug1", "place", "Marcus’s kitchen", "2 clips", "Uploaded for this video", READY, CHG))
bodyB1 = f'<div class="row between"><span class="t-lg">Cast &amp; places</span>{status("need", "Needs you · approve to continue")}</div>{banner1}<div class="col g2">{rowsB1}</div>'
deskB1 = desk_panel(bodyB1, 880, f'<span class="t-sm muted grow">4 characters · 2 places · Mom revised after your note</span>{APPROVE}')
chatB1 = f'''<div class="col g3" style="width:400px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
  {m_dir('<p>Cast and places are ready: 4 characters and 2 places. Check them together in Cast. Storyboards and clips wait until you approve them.</p>', "09:12")}
  {m_me("Mom: warmer, and a bit older.", "09:18", "Reed", "R")}
  {m_dir('<p>Done. Mom’s new look is in Cast, marked “Revised”. Approve the cast and places when the set looks right.</p>', "09:21")}
  <div class="pinbar">{ic("users","s14")}Cast &amp; places waiting for your OK<span class="grow"></span><span class="w6">Show</span></div></div>'''

chase_chg = f'<span class="tag need" style="flex:none">New photo 10:40</span>{was("skit_2")}'
banner2 = f'''<div class="row g2 start t-sm" style="padding:10px 12px;background:var(--warning-soft);color:var(--warning);border-radius:8px;flex:none">{ic("users","s14")}
  <span><b class="w6">Chase changed.</b> Approve the cast and places again before anything new with Chase is made. The other five stay approved, and clips without him carry on.</span></div>'''
clips_old = "".join(media(i, 30, 53, tag=False) for i in ("skit_2", "skit_1", "skit_2"))
affected = f'''<div class="col g2" style="padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);flex:none">
  <div class="row g3"><div class="row g1">{clips_old}</div><div class="col g1 grow"><span class="t-sm w6">Clips 2, 3 and 4 were made with Chase’s old look</span><span class="t-xs muted">They’re kept as they are. After you approve, you choose:</span></div></div>
  <div class="row g2">{btn("Remake clips 2–4 with the new look", "", "refresh-cw", "$2.70")}{btn("Keep them")}</div></div>'''
rowsB2 = (head("Characters", "4") +
          irow("house_marcus_rain", "char", "Marcus", "9 clips", "Made for this video", APPR) +
          irow("sheet_gothgf", "char", "Jade", "3 clips", "From fomo’s library", APPR) +
          irow("still_ugc_still", "char", "Chase", "4 clips", "Uploaded for this video", status("need", "Changed · needs your OK"), CHG, "need", chase_chg) +
          irow("skit_1", "char", "Mom", "1 clip", "Made by the director", APPR) +
          f'<div class="row g2 t-sm muted" style="flex:none">{ic("map-pin","s14")}Places · Bus stop in the rain, Marcus’s kitchen<span class="grow"></span>{APPR}</div>')
bodyB2 = f'<div class="row between"><span class="t-lg">Cast &amp; places</span>{status("need", "Needs you · 1 change")}</div>{banner2}<div class="col g2">{rowsB2}</div>{affected}'
deskB2 = desk_panel(bodyB2, 900, f'<span class="t-sm muted grow">1 change · 5 still approved</span>{APPROVE}')

PAPPROVE = f'<div style="flex:none;padding:10px 14px;border-top:1px solid var(--border);background:var(--surface)">{btn("Approve cast &amp; places", "primary lg", "check").replace("class=", "style=width:100%;justify-content:center class=", 1)}</div>'
pbodyB1 = f'''<div class="col g2" style="padding:12px 14px">{PSEG}
  <div class="row g2 start t-xs" style="padding:8px 10px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px;flex:none">{ic("users","s14")}<span><b class="w6">Check them together.</b> Storyboards and clips wait for your OK.</span></div>
  {irow("house_marcus_rain", "char", "Marcus", "", "Made for this video", READY, phone_=True)}
  {irow("sheet_gothgf", "char", "Jade", "", "fomo’s library", READY, phone_=True)}
  {irow("skit_2", "char", "Chase", "", "Uploaded", READY, phone_=True)}
  {irow("skit_1", "char", "Mom", "", "By the director", READY, phone_=True, extra='<span class="tag new">Revised</span>')}
  {irow("bus", "place", "Bus stop in the rain", "", "Made for this video", READY, phone_=True)}
  {irow("ug1", "place", "Marcus’s kitchen", "", "Uploaded", READY, phone_=True)}
  <span class="t-xs muted">Tap one to see it large or ask for a change.</span></div>'''
pB1 = phone(PTOP(status("need", "Needs you")), pbodyB1, PAPPROVE)
pbodyB2 = f'''<div class="col g2" style="padding:12px 14px">{PSEG}
  <div class="row g2 start t-xs" style="padding:8px 10px;background:var(--warning-soft);color:var(--warning);border-radius:8px;flex:none">{ic("users","s14")}<span><b class="w6">Chase changed.</b> Approve again before anything new with him is made. The rest stay approved.</span></div>
  {irow("still_ugc_still", "char", "Chase", "", "Uploaded", status("need", "Changed"), cls="need", phone_=True, extra=was("skit_2"))}
  <div class="row g2 t-sm muted" style="flex:none;padding:2px 2px">{ic("check","s14")}<span class="grow">Marcus, Jade, Mom and 2 places</span>{APPR}</div>
  <div class="col g2" style="padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--surface);flex:none"><div class="row g2">{clips_old}<span class="t-sm w6">Clips 2–4 used his old look</span></div>
    <span class="t-xs muted">Kept as they are. After you approve:</span>{btn("Remake clips 2–4", "", "refresh-cw", "$2.70")}{btn("Keep them")}</div></div>'''
pB2 = phone(PTOP(status("need", "Needs you")), pbodyB2, PAPPROVE, h=780)
rulesB = box('''<span class="t-xs w6 muted">The rules</span>
  <span>One “Approve cast &amp; places” for the whole set. There is no Approve on a single card, and asking for a look isn’t approving it.</span>
  <span class="muted">The director gathers every character and place (saved, uploaded, made), makes previews within the budget already approved, then pauses. Storyboards and clips that use them wait. The app enforces the pause, not just this screen.</span>
  <span class="muted">Ask for changes in the chat or with Change…; check the revised previews; then approve once.</span>
  <span class="muted">A later change to an approved character or place needs the combined OK again before work that uses it starts again. Unchanged items stay approved, and unrelated work carries on.</span>
  <span class="muted">Clips already made are kept. The director says which would need updating and the price before remaking any.</span>
  <span class="muted">The person making the video approves: an editor approves their own, with no extra owner OK on a published library script. Spending still follows the budget rules (editors see credits). Library sheets keep their own approval (S-gaps-05 L5).</span>''', 440)
s503 = box('''<span class="t-xs w6 muted">S5-03’s line for a brand with no saved characters</span>
  <span class="muted" style="text-decoration:line-through">The director makes looks for this video and asks you to approve them.</span>
  <span>The director prepares the characters and places. Review them together, request any changes, then approve the cast and places to continue.</span>''', 440)
gB = f'''<div class="col g6">
  <div class="row g6 start">{side("Desktop · the chat", chatB1, w=400)}{side("Desktop · 1. The full set, one Mom revised after a note " + EX, deskB1, w=792)}</div>
  <div class="row g6 start">{side("Desktop · 2. Later, after approval: Chase changed " + EX, deskB2, w=792)}{side("Phone · 1. The full set", pB1, w=390)}</div>
  <div class="row g6 start">{side("Phone · 2. A later change", pB2, w=390)}<div class="col g4" style="margin-top:22px">{rulesB}{s503}</div></div></div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 7: the Cast tab</span><span class="t-sm muted" style="max-width:1150px">Two questions from the Cast builder (screen 9, 4 Nov), redrawn to Reed’s answers the same day: A yes, extended; B no, replaced by one combined “Approve cast &amp; places”. They are part of v6. S5-01 to S5-04 and P-09 are extended by this sheet, and S5-03’s line changes as shown. Prices drawn are examples: the app shows the real “up to”, and editors see credits.</span></div>
  <div class="col g8" style="row-gap:40px">
  {cell("A", "Characters and places in the video’s Cast", "The old Cast step had places too. S5 drew only roles. Builder’s proposal: a Places section under the roles, with the same card.", gA,
        [(*OK, "Yes, extended. Places sit alongside characters in the video’s Cast. Each is picked from the library, uploaded, or made for this video only, and labelled with where it came from. Looks the director suggests or makes in the chat show up in the same list. Items made for the video never go into the brand’s library by themselves. Places are settings; Plan decides scenes and action.")])}
  {cell("B", "Approving the cast and places", "Builder’s proposal: “Needs your OK · Approve” on each card. The earlier recommendation: no OK for a look you made yourself. Reed chose neither.", gB,
        [(*OK, "One combined “Approve cast & places”. The full set with previews, a way to request changes and see the revised previews, then one press. Storyboards and clips that use them pause until then. A later change needs the combined OK again; unchanged items stay approved and unrelated work carries on. Clips already made are kept, with the ones needing an update and their price shown first.")])}
  </div>'''

board("S-gaps-07", "Gaps the builders found, part 7", "Approved: characters and places in Cast, one combined Approve cast & places", sheet, "s", h=4460)
