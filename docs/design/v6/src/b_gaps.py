"""S-gaps-01: options for states the v6 boards don't draw (asked by the builders, 3 Nov). For Reed's yes or no."""
from lib import *

W = 640


def cell(n, title, ask, drawn, note):
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px">{drawn}</div>
      <div class="row g2 t-sm"><span class="tag need">For Reed: yes or no?</span><span class="muted">{note}</span></div></div>'''


# 1. Change B-roll look…
looks = [("drp_6", "Glossy 3D anatomy", "Dr. Pickle’s own · default", True), ("sk2", "Inside the body", "from Skeleton", False),
         ("ugcb_4", "Phone-real cutaways", "from UGC", False), ("cl2", "Clay props", "from Claymation", False)]
lk = "".join(f'<div class="col g1" style="width:112px">{media(i, 112, 150, cls="sel" if s else "", tag=False)}<span class="t-sm w6">{t}</span><span class="t-xs muted">{d}</span></div>' for i, t, d, s in looks)
g1 = f'''<div class="card" style="box-shadow:var(--shadow-raised)"><div class="hd"><span class="t-sm w6">B-roll look for this video</span><span class="grow"></span>{ic("x","s14 muted")}</div>
  <div class="bd col g3"><span class="t-sm muted">The B-roll follows the style unless you pick another look here. The presenter and voice don’t change.</span>
  <div class="row g2 start">{lk}</div>
  <div class="row g2">{btn("Use this look", "primary")}{btn("Back to the style’s own")}<span class="grow"></span><span class="t-xs muted">The price on Make it updates</span></div></div></div>'''

# 2. Use a reel · Just its look
g2 = f'''<div style="border:1px solid var(--border-strong);border-radius:14px;background:var(--surface)">
  <div class="row" style="padding:10px 12px 0"><div class="seg"><span>Paste or describe</span><span>From a saved script</span><span class="on">Use a reel</span></div></div>
  <div class="row g3 start" style="padding:12px 14px">{media("drp_1", 60, 107, dur="1:44")}<div class="col g2 grow">
    <div class="row g2">{chip("Copy it shot by shot")}{chip("Just its structure")}{chip("Just its look", None, "check", "on")}</div>
    <span class="t-sm">The director studies the reel’s look: camera, light, colour and cut pace. It makes your script in that look. The reel’s words and story aren’t used.</span>
    <div style="border:1px solid var(--border);border-radius:8px;padding:8px 10px"><span class="t-xs muted">Your script</span><div class="script" style="font-size:12.5px">DR. PICKLE: Your gut after the weekend? A brewery with a pulse.<br><span class="muted">+ 12 more lines</span></div></div></div></div>
  <div class="row g2" style="padding:8px 12px 12px;border-top:1px solid var(--border)">{chip("Presenter","Format")}{chip("from the reel","Look")}<span class="grow"></span>{btn("Make it", "primary", None, "$17.30")}</div></div>
  <span class="t-xs muted" style="display:block;margin-top:6px">Watching the reel is free. The price includes the director’s time studying it.</span>'''

# 3. The upload button in New video
g3 = f'''<div style="position:relative;border:1px solid var(--border-strong);border-radius:14px;background:var(--surface);margin-bottom:84px">
  <div style="padding:12px 14px 8px" class="col g2"><span class="t-sm" style="color:var(--text-faint)">A Dr. Pickle rant about beer bellies, under a minute, ending on the capsule.</span>
    <div class="row g2">{"".join(f'<div class="row g2" style="padding:4px 8px 4px 4px;border:1px solid var(--border);border-radius:6px">{media(i,26,34,tag=False)}<span class="t-xs">{n}</span>{ic("x","s12 muted")}</div>' for i, n in [("ug2", "capsule-pack.jpg"), ("drp_3", "mood-ref.png")])}</div>
    <span class="t-xs muted">Used for this video only. They aren’t added to the brand.</span></div>
  <div class="row g2" style="padding:8px 12px 12px;border-top:1px solid var(--border)"><span class="iconbtn b" style="background:var(--surface-2)">{ic("upload","s14")}</span>{chip("Presenter","Format")}{chip("Dr. Pickle","Style")}<span class="grow"></span>{btn("Make it", "primary", None, "$16.86")}</div>
  <div class="menu" style="left:10px;top:calc(100% + 6px);width:280px"><div class="mi on">{ic("image","s14")}Attach pictures or clips<span class="grow"></span><span class="t-xs muted">for this video</span></div><div class="mi">{ic("film","s14")}Adapt a reel instead…</div></div></div>'''

# 4. Status words beyond the six
rows = [("need", "Needs you", "Start it", "The treatment is posted and waits for Make it"),
        ("need", "Needs you", "Check the scene plan", "The plan waits for an OK or a change"),
        ("need", "Needs you", "Start it", "A video nobody has started yet"),
        ("bad", "Needs a fix", "Stopped at clip 4", "A run that stopped on its own (an error or a limit)"),
        ("stop", "Stopped", "by Reed at 10:14", "Only when a person pressed Stop")]
tb = "".join(f'<div class="lrow" style="padding:9px 12px">{status(k, w)}<span class="t-sm w5" style="width:150px">{r}</span><span class="t-sm muted grow">{d}</span></div>' for k, w, r, d in rows)
cardx = f'''<div class="row g3 start" style="margin-top:12px"><div class="icard" style="width:150px">{media("drp_2",150,200,tag=False)}<span class="t">Beer gut doctor rant</span>{status("need","Needs you")}<span class="m">Start it · up to $16.86</span></div>
  <div class="col g1" style="width:230px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:6px">{"".join(f'<div class="ritem idea"><span class="dot {d}"></span><span class="ell">{t}</span></div>' for d, t in [("need", "Beer gut doctor rant"), ("bad", "Night-time bloat"), ("stop", "Pint vs capsule")])}</div>
  <span class="t-xs muted" style="width:180px">The reason shows after the status on cards, in the folder list and in the header. The tree shows only the dot.</span></div>'''
g4 = f'<div class="list">{tb}</div>{cardx}'

# 5. Sort menu
g5 = f'''<div style="position:relative;height:140px"><div class="row g3">{chip("Newest", "Sort", "list-filter", "on")}<div class="seg"><span class="on">{ic("layers","s14")}</span><span>{ic("list-filter","s14")}</span></div></div>
  <div class="menu" style="left:0;top:36px;width:240px"><div class="mi on">{ic("check","s14")}Newest<span class="grow"></span><span class="t-xs muted">latest activity</span></div>
  <div class="mi"><span style="width:14px"></span>Oldest</div><div class="mi"><span style="width:14px"></span>Name A–Z</div></div></div>'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found</span><span class="t-sm muted">Five states the v6 boards don’t draw. Each is one option for Reed to say yes or no to. The existing boards are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell(1, "“Change B-roll look…” on New video (S2)", "What opens behind the link.", g1, "a small picker. The style’s own look first, then other styles’ B-roll looks.")}
  {cell(2, "Use a reel · “Just its look” (S2-07)", "What the director does with it.", g2, "the reel’s look becomes this video’s look; the words come from the brand’s script.")}
  {cell(3, "The upload button in New video (S2-01)", "What it does.", g3, "attach pictures or clips to the first message, for this video only (rule 12), or switch to Use a reel.")}
  {cell(4, "Status words beyond the six (S0-01)", "Treatment waiting, never started, stopped on its own.", g4, "Needs you plus a short reason; Needs a fix when it stops on its own; Stopped only for a person.")}
  {cell(5, "Sort in a folder (S1-04, S1-05)", "Only Newest is drawn.", g5, "Newest (latest activity), Oldest, Name A–Z.")}
  </div>'''

board("S-gaps-01", "Gaps the builders found", "5 options for Reed: B-roll look, reel look, upload, status words, sort", sheet, "s", h=1580)
