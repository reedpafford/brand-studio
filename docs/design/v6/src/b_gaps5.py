"""S-gaps-05: the library builder's gaps and per-video settings (4 Nov), as Reed decided them."""
from lib import *
from b_s4 import voice_row

W = 640
OK = '<span class="tag ok" style="flex:none">Approved by Reed, 4 Nov</span>'


def cell(n, title, ask, drawn, note):
    return f'''<div class="col g3" style="width:{W}px">
      <div class="col g1"><span class="t-lg">{n}. {title}</span><span class="t-sm muted">{ask}</span></div>
      <div style="padding:16px;background:var(--surface-2);border-radius:10px;position:relative">{drawn}</div>
      <div class="row g2 t-sm start">{OK}<span class="muted">{note}</span></div></div>'''


def card(inner, pad="12px 14px"):
    return f'<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:{pad}" class="col g2">{inner}</div>'


# L1: the Brand kit is short; app screens become a kind of product
kit = card(f'''<div class="row g2"><span class="t-md w6">fomo · Brand kit</span><span class="grow"></span>{btn("Save changes","primary")}</div>
  <div class="row g4"><div class="col g1"><span class="t-xs w6 muted">Name</span><div class="input" style="width:180px;color:var(--text)">fomo</div></div>
    <div class="col g1"><span class="t-xs w6 muted">Logo</span><div class="row g2">{media("fomo_logo",36,36,tag=False)}{btn("Change")}</div></div>
    <div class="col g1"><span class="t-xs w6 muted">Colours</span><div class="row g1">{"".join(f'<i style="width:22px;height:22px;border-radius:5px;background:{c};border:1px solid var(--border)"></i>' for c in ["#000","#fff","#2dd36f","#7c5cff"])}</div></div></div>
  <div class="col g1"><span class="t-xs w6 muted">Tone and rules</span><div class="input" style="height:auto;padding:8px 10px;color:var(--text);font-size:13px">fomo only in a positive light: wins on fomo, losses on plain apps. Always the real fomo UI; numbers can be made up.</div></div>''')
prods = card(f'''<div class="row g2"><span class="t-md w6">Products</span><span class="t-xs muted">examples from two brands: fomo’s app, Iron Paws’ bag (each brand only sees its own)</span></div>
  <div class="row g4 start">
    <div class="col g1" style="width:130px">{media("fomo_token-up",130,200,tag=False)}<div class="row g1"><span class="t-sm w6">fomo app</span><span class="tag n">App</span></div><span class="t-xs muted">10 screens · shown as given; numbers follow the story</span></div>
    <div class="col g1" style="width:130px">{media("ip_bag_pb",130,200,tag=False)}<div class="row g1"><span class="t-sm w6">Peanut butter bag</span><span class="tag n">Physical</span></div><span class="t-xs muted">Iron Paws · the label must read right</span></div>
    <div class="col g2" style="margin-top:4px">{btn("New product","","plus")}<span class="t-xs muted" style="width:150px">An app product holds its screens; a physical one holds its photos.</span></div></div>''')
g1 = f'''{kit}<div style="height:10px"></div>{prods}
  <span class="t-xs muted" style="display:block;margin-top:8px">Gone: end line (the ending comes from the script, rule 18), fonts, style board, script defaults, audience, do / never say, music, legal line, CTA lines, default cast, and the separate “App screens” spot. Archive brand moves to the brand switcher’s menu.</span>'''

# L2: Import from website is dropped
g2 = card(f'''<div class="row g2 t-sm">{ic("x","s14 bad-t")}<span><b class="w6">Import from website is dropped.</b> It only read product names, colours and whether a logo exists, which take a minute to add by hand.</span></div>
  <span class="t-sm muted">So the brand kit has no import button. The set-up list on S1-02 and the import panel on S8-07 lose it too: you add the logo, colours and products yourself.</span>''')

# L3: a saved presenter is a face and a voice; each video picks how they appear
pres = card(f'''<span class="t-md w6">New presenter</span>
  <div class="row g3">{media("still_ugc_still",64,86,tag=False)}<div class="col g2"><div class="input" style="width:200px;color:var(--text)">Name: Mark</div>
    <div class="row g2">{btn("Upload a photo","","upload")}{btn("Pick a saved character","","users")}</div></div></div>
  <div class="row g2"><span class="t-sm w5" style="width:50px">Voice</span>{chip("Roger · relaxed", None, "mic")}<span class="t-xs accent-t">Change</span></div>
  <div class="row g2">{btn("Save presenter","primary")}<span class="t-xs muted">A face and a voice, nothing else.</span></div>''')
ap = [("ugc_2", "Talks to camera", "HeyGen from one still, with B-roll laid over parts", True), ("drp_2", "In a corner over the B-roll", "HeyGen, keyed over the B-roll", False), ("skit_3", "Acts in the story", "Omni: moves, acts, talks to others", False)]
apc = "".join(f'<div class="col g1" style="width:112px">{media(i,112,150,tag=False,cls="sel" if s else "")}<span class="t-sm w6">{t}</span><span class="t-xs muted">{d}</span></div>' for i, t, d, s in ap)
per_video = card(f'''<div class="row g2"><span class="t-sm w6">In the video’s Cast tab: how Mark appears</span><span class="grow"></span><span class="t-xs muted">from the UGC style</span></div>
  <div class="row g3 start">{apc}</div>
  <span class="t-xs muted">The style sets the start: UGC talks to camera, Dr. Pickle sits in the corner, Movie and moving scripts act in the story (Omni). Any mix works: a UGC person can sit in the corner over the B-roll. The director says its pick in the treatment; change it here or in the chat.</span>''')
g3 = f'{pres}<div style="height:10px"></div>{per_video}'

# L4: every voice listed; only uploaded or cloned voices are the brand's
g4 = f'''<div class="col g2"><div class="row g2"><span class="t-sm w6">Voices</span><span class="t-xs muted">every voice plays a free sample</span><span class="grow"></span>{btn("Clone a voice","","upload","$3.00")}</div>
  <span class="t-xs w6 muted">Resilia’s own · uploaded or cloned, saved on purpose</span>{voice_row("Dr. Pickle (cloned)", "Deep, fixed · MiniMax clone", True)}
  <span class="t-xs w6 muted" style="margin-top:4px">The app’s voices · 11 · usable in any video, never saved to a brand</span>
  {voice_row("Sarah", "Warm narrator · ElevenLabs")}{voice_row("Roger", "Relaxed · ElevenLabs")}{voice_row("Calm narrator", "MiniMax")}<span class="t-xs muted">+ 8 more</span></div>'''


# V1: per-video settings at the top of the Plan tab
def sel(k, v, lock=False):
    return f'<span class="chip" style="height:30px">{ic("lock","s12") if lock else ""}<span class="k">{k}</span> {v} {"" if lock else ic("chevron-down","s12")}</span>'


g6 = f'''<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden">
  <div class="tabs" style="padding:0 10px"><span>Cut</span><span>Clips</span><span>Cast</span><span class="on">Plan</span><span>Script</span></div>
  <div style="padding:12px 14px" class="col g2"><div class="row g2"><span class="t-xs w6 muted">This video’s settings</span><span class="grow"></span><span class="t-xs muted">owner and editor · editors see credits</span></div>
  <div class="row g2 wrap">{sel("Shape","9:16")}{sel("Flavour","—")}{sel("Style","Dr. Pickle",True)}{sel("B-roll model","Seedance 1 Lite")}{sel("Presenter","HeyGen")}{sel("Pictures","Nano Banana")}{sel("Language","English")}</div>
  <div class="row g2 t-sm" style="padding:8px 10px;background:var(--accent-soft);color:var(--accent-text);border-radius:6px">{ic("refresh-cw","s14")}<span>B-roll model changed: up to $16.86 → <b class="w6">up to $12.40</b>. The 24 clips not made yet will use it.</span><span class="grow"></span><span class="w6">Undo</span></div></div>
  <div style="padding:0 14px 12px" class="col g1"><span class="t-sm w6">Plan · 6 scenes · 24 clips</span><span class="t-xs muted">1. Hook · 2. What beer does · 3. The bloat · 4. Worse at night · 5. The fix · 6. Ending</span></div></div>
  <div class="col g2" style="margin-top:12px">{m_me("Use Seedance 1 Lite for the B-roll.", "10:06", "Reed", "R")}{m_dir('<p>Done: Seedance 1 Lite for the 24 clips not made yet. The price drops from up to $16.86 to up to $12.40. Undo it in Plan.</p>', "10:06")}</div>'''

# L5: a person approves library sheets
more_rows = "".join(f'<div class="row g3" style="padding:6px 0;border-top:1px solid var(--border)"><span class="t-sm w5" style="width:150px">{k}</span><span class="t-sm muted">{v}</span></div>' for k, v in [("Sheets in other styles", "House, Disney Pixar · the preferred one per style"), ("Outfits", "navy polo (default) · gym kit"), ("Voice sample", "upload a clip of his real voice"), ("History", "v1–v3 · Restore · Delete forever")])
top5 = card(f'''<div class="row g3">{media("still_ugc_still",60,80,tag=False)}<div class="col g1 grow"><div class="row g2"><span class="t-lg">Mark</span>{status("need","Needs your OK")}</div><span class="t-xs muted">Saved to Resilia on purpose. Its sheet needs a person’s OK before videos use it.</span></div>{btn("Approve","primary","check")}{btn("Change this…","","pencil","$0.08")}</div>''')
g5 = f'''{top5}<div style="height:8px"></div>{card('<div class="row g2"><span class="t-sm w6">More</span><span class="grow"></span>' + ic("chevron-down","s14 muted") + '</div>' + more_rows, "10px 14px")}'''

sheet = f'''<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">Gaps the builders found, part 5: the library and video settings</span><span class="t-sm muted">From the library and video-page builders (4 Nov), redrawn to Reed’s answers the same day. The boards they extend are unchanged.</span></div>
  <div class="row g8 wrap start" style="row-gap:36px">
  {cell("L1", "A short Brand kit; products can be apps or things", "Reed: the script and the director carry the rest; an app is just a product.", g1, "Brand kit = name, logo, colours, tone and rules. Products hold apps (their screens) and physical items (their photos). Everything else goes; rule 18 becomes “the ending comes from the script”.")}
  {cell("L2", "Import from website", "Reed: “Lets drop it entirely.”", g2, "No import anywhere.")}
  {cell("L3", "A presenter is a face and a voice; each video picks how they appear", "Reed: the style sets it, but any mix works (a UGC person in the corner over B-roll).", g3, "Saved presenter = face + voice. Per video: Talks to camera or In a corner (HeyGen), or Acts in the story (Omni); the style picks first; change it in the Cast tab or the chat.")}
  {cell("L4", "Voices", "Reed: list every voice; save only voices uploaded or cloned on purpose.", g4, "Every app voice is listed with a free sample and usable anywhere; a brand’s own voices are only the ones uploaded or cloned and saved.")}
  {cell("V1", "Per-video settings (the Plan tab)", "Keeps Reed’s “the option to change models for each ad” (3 Nov).", g6, "At the top of the Plan tab for every video, owner and editor (editors see credits), with the new price and Undo; the director also changes them when asked in the chat.")}
  {cell("L5", "Item page: a person approves library sheets", "Reed: characters are added to a brand only on purpose, so a person approves.", g5, "S8-03 on top with “Needs your OK · Approve” until approved; the rest under “More”.")}
  </div>'''

board("S-gaps-05", "Gaps the builders found, part 5", "Approved: short brand kit, no import, presenter = face + voice, every voice, video settings, a person approves sheets", sheet, "s", h=2260)
