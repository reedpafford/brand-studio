"""S-gaps-05: the library builder's gaps (4 Nov), with Reed's decisions marked. For Reed's yes or no."""
from lib import *
from b_s4 import voice_row

W = 640


def cell(n, title, ask, drawn, note, q=None):
    qq = f'<div class="row g2 t-sm start" style="padding:8px 10px;background:var(--warning-soft);border-radius:8px;color:var(--warning)">{ic("circle-question-mark","s14")}<span><b class="w6">Reed decides:</b> {q}</span></div>' if q else ""
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="row g2 t-sm start"><span class="tag need" style="flex:none">For Reed: yes or no?</span><span class="muted">{note}</span></div>{qq}</div>'''


def fold(title, rows, open_=True):
    r = "".join(f'<div class="row g3" style="padding:7px 0;border-top:1px solid var(--border)"><span class="t-sm w5" style="width:150px;flex:none">{k}</span><span class="t-sm muted grow">{v}</span></div>' for k, v in rows)
    return f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 14px">
      <div class="row g2"><span class="t-sm w6">{title}</span><span class="grow"></span>{ic("chevron-down" if open_ else "chevron-right","s14 muted")}</div>{r if open_ else ""}</div>'''


# L1 Brand kit: drawn part on top, the rest under More
top = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 14px" class="col g2">
  <div class="row g3">{media("fomo_logo",36,36,tag=False)}<span class="t-sm w6">Logo · Colours · End line · Tone and rules · App screens</span></div><span class="t-xs muted">As drawn on S8-05</span></div>'''
more = fold("More", [("Name and fonts", "fomo · Manrope"), ("Style board", "one picture of the brand’s mood"), ("New scripts start with", "House style · English"),
                     ("Audience", "traders 20–35, US"), ("Do say / Never say", "2 lists"), ("Music style", "dark trap, low"), ("Legal line", "“Not financial advice.”"),
                     ("CTA lines", "3 saved, one is the default"), ("Default cast", "Goth GF")])
sw = f'''<div class="menu" style="position:static;width:230px;margin-top:10px"><div class="mi">{BRANDS["fomo"]}fomo</div><div class="mi">{BRANDS["Resilia"]}Resilia</div><div class="sepm"></div><div class="mi">{ic("plus","s14")}New brand</div><div class="mi">{ic("archive","s14")}Archive this brand…</div></div>'''
g1 = f'{top}<div style="height:8px"></div>{more}<div class="row g3 start">{sw}<span class="t-xs muted" style="margin-top:16px;width:300px">Archive brand moves to the brand switcher’s menu (owner only).</span></div>'

# L2 Import from website
g2 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 14px" class="row g2">
  <span class="t-sm w6">fomo · Brand kit</span><span class="grow"></span>{btn("Import from website", "", "globe")}{btn("Save changes", "primary")}</div>
  <div class="col g2" style="margin-top:12px;width:420px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px">
  <span class="t-sm w6">Import from the brand’s website</span><div class="input" style="color:var(--text)">{ic("globe","s14")}fomo.app</div>
  <div class="row g2">{btn("Read the website", "primary", None, "$0.11")}<span class="t-xs muted">You approve each item before it’s saved.</span></div></div>
  <span class="t-xs muted" style="display:block;margin-top:8px">S8-07’s note said “Free”; a read costs about 1 credit ($0.11) today. Editors see “up to 1 credit”. The set-up list (S1-02) links here.</span>'''

# L3 New presenter, and S5-02's "how it appears" against the model map
ap = [("ugc_2", "Still talking head", "HeyGen, from one still"), ("drp_2", "In a corner over the B-roll", "HeyGen, keyed over the B-roll"), ("skit_3", "Acts in the story", "Omni: moves, acts, talks to others")]
apc = "".join(f'<div class="col g1" style="width:120px">{media(i,120,160,tag=False,cls="sel" if n == 0 else "")}<span class="t-sm w6">{t}</span><span class="t-xs muted">{s}</span></div>' for n, (i, t, s) in enumerate(ap))
g3 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 14px" class="col g3">
  <span class="t-md w6">New presenter</span>
  <div class="row g3"><div class="input" style="width:200px;color:var(--text)">Name: Mark</div>{btn("Upload a photo","","upload")}{btn("Pick a saved character","","users")}</div>
  <div class="row g2"><span class="t-sm w5" style="width:60px">Voice</span>{chip("Roger · relaxed","", "mic")}<span class="t-xs accent-t">Change</span></div>
  <span class="t-sm w6">How it appears</span><div class="row g3 start">{apc}</div>
  <div class="row g2">{btn("Save presenter","primary")}<span class="t-xs muted">Saving is free. Each video prices its talker.</span></div></div>
  <span class="t-xs muted" style="display:block;margin-top:8px">The same three cards replace S5-02’s, whose “Made with: P-Video” is out of date under Reed’s current model map.</span>'''

# L4 Voices: the brand's own, with Add from the app's list, and Clone
add = f'''<div class="menu" style="position:static;width:300px"><div class="mi"><span class="t-xs muted">Add a voice to Resilia · samples play free</span></div>
  {"".join(f'<div class="mi">{ic("play","s12")}<span class="grow">{n}</span><span class="t-xs muted">{p}</span></div>' for n, p in [("Sarah", "ElevenLabs · warm"), ("Austin", "ElevenLabs · deep"), ("Roger", "ElevenLabs · relaxed"), ("Calm narrator", "MiniMax"), ("+ 7 more", "")])}
  <div class="sepm"></div><div class="mi">{ic("upload","s14")}Clone a voice…<span class="grow"></span><span class="t-xs muted">up to $3.00</span></div></div>'''
clone = f'''<div class="col g2" style="width:270px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px"><span class="t-sm w6">Clone a voice</span>
  <div class="row g2" style="padding:8px;border:1px dashed var(--border-strong);border-radius:6px">{ic("upload","s14")}<span class="t-xs">doctor-sample.mp3 · 14 s</span></div>
  <span class="t-xs muted">At least 10 s of one clear voice.</span><div class="input" style="color:var(--text)">Name: Dr. Pickle</div>
  {btn("Clone · up to $3.00","primary")}</div>'''
g4 = f'''<div class="col g2"><span class="t-xs w6 muted">Resilia’s voices (option b)</span><div class="col g2" style="width:560px">{voice_row("Dr. Pickle (cloned)", "Deep, fixed · MiniMax clone", True)}{voice_row("Roger", "Relaxed · ElevenLabs · saved")}</div>
  <div class="row g3 start" style="margin-top:6px">{add}{clone}</div></div>'''

# L5 Item page: S8-03 on top, More below; the sheet's OK
g5 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 14px" class="row g3">{media("still_ugc_still",60,80,tag=False)}
  <div class="col g1 grow"><div class="row g2"><span class="t-lg">Mark</span>{status("need","Needs your OK")}</div><span class="t-xs muted">As drawn on S8-03, with the sheet’s OK where “In use” sits</span></div>{btn("Approve","primary","check")}{btn("Change this…","","pencil","$0.08")}</div>
  <div style="height:8px"></div>{fold("More", [("Sheets in other styles", "House, Disney Pixar · the preferred one per style marked"), ("Outfits", "navy polo (default) · gym kit"), ("Voice sample", "upload a clip of his real voice"), ("Shared with brands", "Resilia only"), ("History", "v1–v3 · Restore · Delete forever")])}'''

# V1 Per-video settings at the top of the Plan tab
def sel(k, v, lock=False):
    return f'<span class="chip" style="height:30px">{ic("lock","s12") if lock else ""}<span class="k">{k}</span> {v} {"" if lock else ic("chevron-down","s12")}</span>'


settings = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden">
  <div class="tabs" style="padding:0 10px"><span>Cut</span><span>Clips</span><span>Cast</span><span class="on">Plan</span><span>Script</span></div>
  <div style="padding:12px 14px" class="col g2"><div class="row g2"><span class="t-xs w6 muted">This video’s settings</span><span class="grow"></span><span class="t-xs muted">owner and editor · editors see credits</span></div>
  <div class="row g2 wrap">{sel("Shape","9:16")}{sel("Flavour","—")}{sel("Style","Dr. Pickle",True)}{sel("B-roll model","Seedance 1 Lite")}{sel("Host","HeyGen")}{sel("Pictures","Nano Banana")}{sel("Language","English")}</div>
  <div class="row g2 t-sm" style="padding:8px 10px;background:var(--accent-soft);color:var(--accent-text);border-radius:6px">{ic("refresh-cw","s14")}<span>B-roll model changed: up to $16.86 → <b class="w6">up to $12.40</b>. 24 clips not made yet will use it.</span><span class="grow"></span><span class="w6">Undo</span></div></div>
  <div style="padding:0 14px 12px" class="col g1"><span class="t-sm w6">Plan · 6 scenes · 24 clips</span>{"".join(f'<span class="t-xs muted">{i+1}. {n}</span>' for i, n in enumerate(["Hook", "What beer does", "The bloat", "Worse at night", "The fix", "Ending"]))}</div></div>
  <div class="col g2" style="margin-top:12px">{m_me("Use Seedance 1 Lite for the B-roll.", "10:06", "Reed", "R")}{m_dir('<p>Done: the B-roll model is Seedance 1 Lite for the 24 clips not made yet. The price drops from up to $16.86 to up to $12.40. Undo it in Plan.</p>', "10:06")}</div>'''
g6 = settings

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 5: the library and video settings</span><span class="t-sm muted">Five gaps from the library builder and one from the video-page builder (4 Nov). Each is one option for Reed to say yes or no to; four need a decision, marked in amber. The existing boards are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell("L1", "Brand kit keeps every field (S8-05)", "S8-05 draws 5 fields; today’s brand page has more. Dropping them would be weaker.", g1, "S8-05 as drawn on top, a “More” fold below with every other field; Archive brand moves to the brand switcher’s menu.")}
  {cell("L2", "Import from website (S8-07)", "No drawn trigger, and its note says “Free”, but a read costs about 1 credit.", g2, "An “Import from website” button on the Brand kit tab (owner) opens the S8-07 panel; the set-up list links there; the price shows first.", "keep the read priced (about $0.11), or make it free?")}
  {cell("L3", "New presenter, and how a presenter appears (S8-04, S5-02)", "S8-04 stops at the button; S5-02 still says P-Video.", g3, "New character’s form plus “how it appears” cards: Still talking head = HeyGen; In a corner over the B-roll = HeyGen keyed; Acts in the story = Omni. S5-02’s cards follow.", "is the corner-over-B-roll host (Dr. Pickle) HeyGen too, as drawn?")}
  {cell("L4", "Voices (S8-04)", "Which list, and the Clone flow.", g4, "Option (b), recommended: the library shows the brand’s own voices; “Add a voice” opens the app’s 11 voices with free samples, plus Clone (sample of 10 s or more, a name, price first).", "(b) the brand’s voices with Add (recommended), or (a) every app voice listed in the library?")}
  {cell("V1", "Per-video settings (the Plan tab)", "Not on any v6 board, but Reed asked for “the option to change models for each ad” (3 Nov).", g6, "Kept at the top of the Plan tab for every video, owner and editor (editors see credits), with the new price and Undo. The director also changes them when asked in the chat, and says the new price.")}
  {cell("L5", "Item page keeps everything (S8-03)", "Today’s item page has more than S8-03 draws.", g5, "S8-03 exactly on top, the rest under “More”. A sheet that still needs an OK shows “Needs your OK · Approve” where the board has “In use”.", "library sheets are made by a person in Cast & places: keep a person’s OK on them (recommended), or let the director approve clean ones as in videos (rule 21)?")}
  </div>'''

board("S-gaps-05", "Gaps the builders found, part 5", "6 options for Reed (4 decisions): brand kit, import, new presenter, voices, video settings, item page", sheet, "s", h=2260)
