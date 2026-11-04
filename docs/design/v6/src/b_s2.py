"""S2: New video. One message box that becomes the video's chat, with picture cards for format and style."""
from lib import *
from b_s01 import FOLDER_TREE

FORMATS = [("Dialogue", "skit_2", "People talk on camera"), ("Song", "px2", "A song with pictures to it"),
           ("Narrated", "sk1", "One voice over B-roll"), ("Presenter", "drp_2", "A host over B-roll")]
STYLES = [("House", "house_marcus_rain", "Our caricatured 3D", "B-roll: near-real inserts"), ("Disney Pixar", "px1", "Warm, appealing 3D", "B-roll: toy-like body worlds"),
          ("Claymation", "cl1", "Handmade clay", "B-roll: clay props"), ("Skeleton", "sk2", "Glass-body skeleton", "B-roll: inside the body"),
          ("Zack D", "zd1", "One moving camera", "B-roll: game-engine 3D"), ("Dr. Pickle", "drp_1", "Clay doctor over anatomy", "B-roll: glossy 3D anatomy"),
          ("UGC", "ugc_1", "Phone-real talker", "B-roll: phone-real cutaways"), ("Movie", "skit_1", "Photoreal drama", "Coming · 6–9 min dramas")]


def fcard(name, img, sub, sel=False, off=False):
    return f'''<div class="stylecard{" sel" if sel else ""}{" off" if off else ""}" style="width:200px">{media(img, 200, 84, style="border-radius:0")}
      <div class="info"><div class="row g2"><span class="t-sm w6">{name}</span><span class="grow"></span>{('<span class="tag n">coming next</span>' if off else (ic("circle-check-big","s14 accent-t") if sel else ""))}</div><span class="t-xs muted">{sub}</span></div></div>'''


def scard(name, img, sub, broll, sel=False, off=False, playing=False, offwhy=None):
    play = f'<span class="play"><i>{ic("pause" if playing else "play","s14")}</i></span>'
    prog = '<div style="position:absolute;left:6px;right:6px;bottom:6px" class="prog"><i style="width:40%;background:#fff"></i></div>' if playing else ""
    return f'''<div class="stylecard{" sel" if sel else ""}{" off" if off else ""}" style="width:132px">{media(img, 132, 150, extra=play + prog, style="border-radius:0")}
      <div class="info"><div class="row g1"><span class="t-sm w6">{name}</span><span class="grow"></span>{ic("circle-check-big","s14 accent-t") if sel else ""}</div><span class="t-xs muted">{sub}</span><span class="t-xs" style="color:var(--text-muted)">{broll}</span>{f'<span class="tag n" style="margin-top:4px;align-self:flex-start">{offwhy}</span>' if offwhy else ""}</div></div>'''


def composer_big(text=None, price=None, editor=False, held=False, tab="Paste or describe", fmt="Presenter", sty="Dr. Pickle", main=None):
    tabs = "".join(f'<span class="{"on" if t == tab else ""}">{t}</span>' for t in ["Paste or describe", "From a saved script", "Use a reel"])
    if text:
        body = f'<div class="script" style="font-size:13px;line-height:1.6;color:var(--text);min-height:96px">{text}</div>'
    else:
        body = '<div style="min-height:96px;color:var(--text-faint);font-size:15px">Paste a script, or describe the video. “A Dr. Pickle rant about beer bellies, under a minute, ending on the capsule.”</div>'
    chips = "".join([chip(fmt, "Format"), chip(sty, "Style"), chip("Dr. Pickle", "Cast", "users"), chip("9:16", "Shape"), chip("Week of 3 Nov", "Folder", "folder")])
    if main is None:
        if not text:
            main = btn("Make it", "dis lg")
        elif held:
            main = btn("Send to the owner", "primary lg", "arrow-up", price)
        else:
            main = btn("Make it", "primary lg", None, price)
    under = ""
    if text and not held:
        under = f'<span class="t-xs muted">{"Most it can charge, including redos and the director’s time. Usually less." if not editor else "Inside this video’s budget, so it starts straight away."}</span>'
    elif held:
        under = '<span class="t-xs warn-t row g1">' + ic("clock", "s12") + ' The owner approves before anything is spent. You’ll see it in My requests.</span>'
    return f'''<div style="border:1px solid var(--border-strong);border-radius:14px;background:var(--surface);box-shadow:var(--shadow-soft)">
      <div class="row" style="padding:10px 12px 0"><div class="seg">{tabs}</div></div>
      <div style="padding:14px 16px 8px">{body}</div>
      <div class="row g2 wrap" style="padding:8px 12px 12px;border-top:1px solid var(--border)"><span class="iconbtn">{ic("upload","s14")}</span>{chips}<span class="grow"></span>{main}</div></div>
      <div class="row" style="padding:6px 4px;min-height:24px">{under}</div>'''


SCRIPT = "DR. PICKLE: Your gut after the weekend? A brewery with a pulse.<br>DR. PICKLE: Every pint sits there and ferments.<br>DR. PICKLE: That’s not a belly. That’s a science project.<br>DR. PICKLE: And at 3 AM? It throws a party.<br><span class=\"muted\">+ 9 more lines · 142 words · about 58 s</span>"


def page(comp, fsel="Presenter", ssel="Dr. Pickle", playing="Dr. Pickle", off=("Song",), role="owner", note="", soff=()):
    fc = "".join(fcard(n, i, s, n == fsel, n in off) for n, i, s in FORMATS)
    sc = "".join(scard(n, i, s, b, n == ssel, n == "Movie" or n in soff, n == playing, "Off on this site" if n in soff else None) for n, i, s, b in STYLES)
    return rail(tree=FOLDER_TREE, role=role) + f'''<main class="main"><div class="ptop"><div class="crumb">Resilia {ic("chevron-right","s12")} <b>New video</b></div></div>
      <div style="overflow:hidden;padding:20px 0;display:flex;justify-content:center"><div class="col g4" style="width:1112px">
        <div class="col g1"><span class="t-2xl">What should the director make?</span><span class="t-md muted">Paste a script or describe it. The director plans it, asks what it can’t decide, and makes it in a chat with you.</span></div>
        <div>{comp}</div>
        <div class="col g2"><div class="row g2"><span class="t-sm w6">Format</span><span class="t-xs muted">How the words are delivered</span></div><div class="row g3 start">{fc}</div></div>
        <div class="col g2"><div class="row g2"><span class="t-sm w6">Style</span><span class="t-xs muted">How it looks and how the camera moves. The B-roll follows the style.</span><span class="grow"></span><span class="t-xs accent-t w5">Change B-roll look…</span></div><div class="row g2 start">{sc}</div></div>
        {note}
      </div></div></main>'''


board("S2-01", "New video", "Empty", page(composer_big(), playing=None))
board("S2-02", "New video", "Filled in · a style sample playing · price shown (owner)", page(composer_big(SCRIPT, "up to $16.86")))
off_note = f'<div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("circle-question-mark","s14 muted")}<span><b class="w6">Song</b> is coming next: its music provider isn’t switched on for this site yet. <b class="w6">Movie</b> is coming: 6–9 minute photoreal dramas on Omni.</span><span class="grow"></span><span class="t-sm accent-t w5">Settings → Looks</span></div>'
off_note = off_note.replace("<b class=\"w6\">Movie</b> is coming: 6–9 minute photoreal dramas on Omni.", "<b class=\"w6\">Movie</b> is coming: 6–9 minute photoreal dramas on Omni. <b class=\"w6\">UGC</b> is off on this site; the owner turns it on in Settings → Looks.")
board("S2-03", "New video", "A format and a style that are off", page(composer_big(SCRIPT, "up to $16.86"), off=("Song",), note=off_note, soff=("UGC",), playing=None))
board("S2-04", "New video", "Editor’s pasted script · held for the owner", page(composer_big(SCRIPT, "up to 164 credits", editor=True, held=True), role="editor"))
over = composer_big(SCRIPT, None, editor=True, tab="From a saved script", main=btn("Send to the owner", "primary lg", "arrow-up", "up to 212 credits")).replace(
    "</div>\n      <div class=\"row\" style=\"padding:6px 4px;min-height:24px\"><span class=\"t-xs muted\">Inside this video’s budget, so it starts straight away.</span></div>",
    '</div>\n      <div class="row" style="padding:6px 4px;min-height:24px"><span class="t-xs warn-t row g1">' + ic("clock", "s12") + ' Up to 212 credits is past this video’s budget of 194, so it goes to the owner first. Nothing is spent while it waits.</span></div>')
board("S2-05", "New video", "Editor · over the video’s budget · held", page(over, role="editor"))


def from_script():
    rows = [("Beer gut doctor rant", "Published · v2 · 13 lines", "Dr. Pickle", "1 of 3 videos made"), ("Why IPAs hit harder", "Published · v1 · 11 lines", "Dr. Pickle", "2 of 3 videos made"),
            ("Bloated after pizza", "Published · v1 · 8 lines", "UGC", "none made yet"), ("Gut glow-up", "Draft · v3", "Claymation", "owner only")]
    lst = "".join(f'<div class="lrow{" sel" if i == 0 else ""}" style="padding:10px 12px"><span class="check{" on" if i == 0 else ""}" style="border-radius:50%">{ic("check","s12") if i == 0 else ""}</span>{ic("file-text","s14 muted")}<div class="col grow"><span class="w6">{t}</span><span class="t-xs muted">{s}</span></div><span class="t-sm muted" style="width:90px">{st}</span><span class="t-sm muted" style="width:130px;text-align:right">{u}</span></div>' for i, (t, s, st, u) in enumerate(rows))
    comp = f'''<div style="border:1px solid var(--border-strong);border-radius:14px;background:var(--surface);box-shadow:var(--shadow-soft)">
      <div class="row g3" style="padding:10px 12px 0"><div class="seg"><span>Paste or describe</span><span class="on">From a saved script</span><span>Use a reel</span></div><div class="input" style="height:30px;width:260px">{ic("search","s14")}Search Resilia’s scripts</div></div>
      <div style="padding:12px 12px 8px"><div class="list">{lst}</div></div>
      <div class="row g2" style="padding:8px 12px 12px;border-top:1px solid var(--border)"><span class="t-sm muted">The script’s words are set. The director can still add a note: “end on the capsule”.</span><span class="grow"></span>{btn("Make it", "primary lg", None, "up to $16.86")}</div></div>'''
    return page(comp, playing=None)


def use_reel():
    comp = f'''<div style="border:1px solid var(--border-strong);border-radius:14px;background:var(--surface);box-shadow:var(--shadow-soft)">
      <div class="row" style="padding:10px 12px 0"><div class="seg"><span>Paste or describe</span><span>From a saved script</span><span class="on">Use a reel</span></div></div>
      <div class="row g4" style="padding:14px 16px">{media("drp_1", 72, 128, dur="1:44")}<div class="col g2 grow"><span class="w6">doctor-rant-reference.mp4</span><span class="t-sm muted">1:44 · uploaded · the director watches and listens to it, then writes a script that keeps its shape with Resilia’s product</span>
        <div class="row g2">{chip("Copy it shot by shot", None, "copy", "on")}{chip("Just its structure", None)}{chip("Just its look", None)}</div>
        <span class="t-xs muted">Live-action parts are swapped for the brand’s ending.</span></div></div>
      <div class="row g2" style="padding:8px 12px 12px;border-top:1px solid var(--border)"><span class="iconbtn">{ic("upload","s14")}</span>{chip("Presenter","Format")}{chip("Dr. Pickle","Style")}<span class="grow"></span>{btn("Watch it and write the script", "primary lg", None, "up to $0.40")}</div></div>'''
    return page(comp, playing=None)


board("S2-06", "New video", "From a saved script", from_script())
board("S2-07", "New video", "Use a reel", use_reel())
