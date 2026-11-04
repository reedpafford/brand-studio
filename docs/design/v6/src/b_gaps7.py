"""S-gaps-07: two Cast-tab details the boards leave open (the Cast builder, screen 9, 4 Nov). For Reed's yes or no."""
from lib import *
from b_s56 import role_card
from b_phone import vtop

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


def phone(top, body, h=760):
    """A 390 phone at 1x, cut off at h. (class order "p screen" keeps render.py from treating the sheet as a phone board.)"""
    return f'''<div class="p screen" style="height:{h}px;border:1px solid var(--border);border-radius:14px;flex:none">{phone_status()}{top}
      <div class="pbody">{body}</div><div class="home-ind"><i></i></div></div>'''


def desk_panel(body, h, cast_n="6"):
    tabs = [("Cut", None), ("Clips", "9"), ("Cast", cast_n), ("Plan", None), ("Script", None)]
    return f'<div style="width:792px;height:{h}px;display:flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;flex:none">{panel("Cast", body, tabs)}</div>'


PTOP = vtop("Three dimes to a penthouse", status("need", "Needs you"), on="Preview").replace("up to $16.86", "up to $19.40")
PSEG = '<div class="seg" style="flex:none"><span>Cut</span><span>Clips</span><span class="on">Cast</span><span>Plan</span><span>Script</span></div>'


def prole(img, name, sub, st, acts="", cls=""):
    pic = bus_stop(60, 80, 190) if img == "bus" else (media(img, 60, 80, tag=False) if img else empty_media(60, 80))
    a = f'<div class="row g2 wrap" style="margin-top:6px">{acts}</div>' if acts else ""
    return f'<div class="role {cls}" style="padding:10px;flex:none">{pic}<div class="col g1 grow"><span class="w6">{name}</span><span class="t-xs muted">{sub}</span>{st}{a}</div></div>'


def bus_stop(w, h, iw):
    """The rain frame's top-left corner (street lamp, rain, the shelter), without Marcus in it."""
    return f'<div class="media" style="width:{w}px;height:{h}px"><img src="{src("house_marcus_rain")}" style="width:{iw}px;height:auto;max-width:none;object-fit:fill"></div>'


def place_pic(img, w=150, h=100):
    if img == "bus":
        return bus_stop(w, h, 267)
    return media(img, w, h, tag=False) if img else empty_media(w, h, "empty", f'<span class="play" style="color:var(--warning)">{ic("map-pin","s20")}</span>')


def place_card(img, name, where, src, state_html, actions="", cls=""):
    return f'''<div class="role {cls}">{place_pic(img)}<div class="col g2 grow"><div class="row g2"><span class="w6 t-md">{name}</span><span class="t-sm muted">{where}</span><span class="grow"></span>{state_html}</div>
      <span class="t-sm muted">{src}</span><div class="row g2 wrap">{actions}</div></div></div>'''


# ---------- A. Places in the Cast tab ----------
marcus = role_card("house_marcus_rain", "Marcus", "Main character · in 9 of 9 clips", "Look made for this video · not in the library", status("ok", "Approved"),
                   btn("Change this…", "", "pencil") + btn("Lock", "", "lock"))
jade = role_card("sheet_gothgf", "Jade", "Girlfriend · in 3 clips", "Saved in fomo: “Goth GF” v4", status("ok", "Locked"), btn("Unlock", "", "lock"))
bus = place_card("bus", "Bus stop in the rain", "in 4 clips", "Look made for this video · not in the library", status("ok", "Approved"),
                 btn("Change this…", "", "pencil") + btn("Lock", "", "lock"))
pent = place_card(None, "The penthouse", "in 3 clips", "No look yet. Clips 7–9 wait for it.", status("need", "Needs a look"),
                  btn("Pick from fomo’s places", "primary", "map-pin") + btn("Upload", "", "upload") + btn("Make a look", "", "wand-sparkles", "$0.08"), cls="need")
bodyA = f'''<div class="row between"><span class="t-lg">Cast</span><span class="t-sm muted">4 roles · 2 places</span></div>
  <div class="col g3">{marcus}{jade}<span class="t-xs muted" style="padding-left:2px">+ Chase and Mom, as on S5-01</span></div>
  <div class="row between" style="margin-top:6px"><span class="t-lg">Places</span><span class="t-sm muted">each drawn once, so every clip there matches</span></div>
  <div class="col g3">{bus}{pent}</div>'''
deskA = desk_panel(bodyA, 820)
pbodyA = f'''<div class="col g2" style="padding:12px 14px">{PSEG}
  <div class="row between" style="margin-top:6px"><span class="t-sm w6">Cast</span><span class="t-xs muted">4 roles</span></div>
  {prole("house_marcus_rain", "Marcus", "Look for this video", status("ok", "Approved"))}{prole("sheet_gothgf", "Jade", "Saved in fomo", status("ok", "Locked"))}
  <span class="t-xs muted">+ Chase and Mom</span>
  <div class="row between" style="margin-top:6px"><span class="t-sm w6">Places</span><span class="t-xs muted">2 places</span></div>
  {prole("bus", "Bus stop in the rain", "Look for this video · 4 clips", status("ok", "Approved"))}
  {prole(None, "The penthouse", "Clips 7–9 wait for it", status("need", "Needs a look"), btn("Pick", "primary", "map-pin") + btn("Upload", "", "upload") + btn("Make", "", "wand-sparkles", "$0.08"), "need")}</div>'''
pA = phone(PTOP, pbodyA, h=844)
gA = f'''<div class="row g6 start">
  {side("Desktop · S5-01’s Cast tab with a Places section under the roles", deskA, "The tab keeps its short name, Cast; its count adds the places (4 roles + 2 places = 6). A place card is the role card with a wide picture: where it came from, its state, and the same presses.", 792)}
  {side("Phone · P-09 with the same section", pA, "Same cards, same order: roles, then places.", 390)}</div>'''

# ---------- B. A look a person made ----------
chase_drawing = role_card(None, "Chase", "Rival · in 4 clips", "Drawing the look you asked for · up to $0.08 · about 30 s", status("work", "Drawing"), btn("Cancel"),
                          imgs=f'<div class="row g1">{empty_media(42,118,"working")}{empty_media(42,118,"working")}{empty_media(42,118,"working")}</div>')
chase_done = role_card("skit_2", "Chase", "Rival · in 4 clips", "Look you made for this video · 09:14 · not in the library", status("ok", "Approved"),
                       btn("Change this…", "", "pencil", "$0.08") + btn("Lock", "", "lock"))
chat = f'''<div class="col g2" style="width:600px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
  {m_me("Make Chase: early 30s, sharp suit, smug grin.", "09:13", "Reed", "R")}
  {sysline("check", "Chase’s look is in. Clips 2–4 are starting.")}</div>'''
deskB = f'''<div class="col g3" style="width:640px">
  <span class="t-xs w6 muted">1 · You pressed Make a look (or Change this…)</span>{chase_drawing}
  <span class="t-xs w6 muted" style="margin-top:6px">2 · Drawn: used straight away, no OK</span>{chase_done}
  <span class="t-xs w6 muted" style="margin-top:6px">In the chat</span>{chat}</div>'''
pbodyB = f'''<div class="col g2" style="padding:12px 14px">{PSEG}
  <div class="row between" style="margin-top:6px"><span class="t-sm w6">Cast</span><span class="t-xs muted">4 roles</span></div>
  {prole("house_marcus_rain", "Marcus", "Look for this video", status("ok", "Approved"))}{prole("sheet_gothgf", "Jade", "Saved in fomo", status("ok", "Locked"))}
  {prole("skit_2", "Chase", "Look you made · 09:14", status("ok", "Approved"), btn("Change this…", "", "pencil", "$0.08"))}
  {prole("skit_3", "Mom", "Look for this video", status("ok", "Approved"))}</div>'''
pB = phone(PTOP.replace(status("need", "Needs you"), status("work", "Working")), pbodyB, h=640)
slip = f'''<div class="col g2 t-sm" style="padding:12px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;width:250px">
  <span class="t-xs w6 muted">Why no OK</span>
  <span>Pressing Make a look or Change this… is already the decision. The director’s own looks go straight in too (rule 21).</span>
  <span class="muted">A library sheet still needs Approve (S-gaps-05 L5): it’s saved to the brand for every video. A look here stays with this video.</span>
  <span class="muted">If the director’s check finds a flaw, it redraws it, as with its own looks. Clips already made with an old look are only remade if you say so; it asks first, with the price.</span>
  <span class="t-xs w6 muted" style="margin-top:6px">A slip to fix either way</span>
  <span class="muted">S5-03’s empty-brand line says the director “asks you to approve” its looks. Under rule 21 it should read “The director makes looks for this video and checks them itself.”</span></div>'''
gB = f'''<div class="row g6 start">
  {side("Desktop · the role card (S5-03’s states)", deskB, w=640)}
  {side("Phone · P-09 once it’s drawn", pB, w=390)}
  {slip}</div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 7: the Cast tab</span><span class="t-sm muted" style="max-width:1100px">Two questions from the Cast builder (screen 9, 4 Nov), drawn at full size: desktop (1440) and phone (390) side by side. Where an approved board already settles a point, the sheet says so and draws it as that board has it. Everything else is one recommended option, for Reed’s yes or no. The boards they extend are unchanged until Reed answers.</span></div>
  <div class="col g8" style="row-gap:40px">
  {cell("A", "Places in the Cast tab", "The old Cast step had Places too (make, approve or change a look). S5 draws only roles. Builder’s proposal: a Places section under the roles, with the same card.", gA,
        [("ok", "Already specified by S5-01 to S5-04 and S-gaps-05", "Cast holds no products or app screens: the plan and the Locks pick them, and Flavour sits in the Plan tab’s settings row (V1)."),
         (*ASK, "A Places section under the roles, with the same card: picture, state, Change this… or Pick / Upload / Make a look · up to $0.08. Why: a place drawn once keeps every clip there the same, and it fixes the same way as a role.")])}
  {cell("B", "A look you made yourself: does it need your OK?", "Make a look or Change this…, drawn and waiting. S5-03 has no “needs your OK” state. Builder’s proposal: S-gaps-05 L5’s “Needs your OK · Approve” on the role card.", gB,
        [("ok", "Already specified by rule 21 and S5-03", "the director approves its own clean work; a role goes Drawing → Approved with no person’s OK in between."),
         (*ASK, "No OK: a look you made is used as soon as it’s drawn, and the clips waiting for it start. “Change this… · up to $0.08” stays on the card. Why: you already decided by pressing it, and an Approve step would only hold the clips up.")])}
  </div>'''

board("S-gaps-07", "Gaps the builders found, part 7", "2 options for Reed: Places in the Cast tab, no OK for a look you made", sheet, "s", h=2120)
