"""S8 brand library; S9 Needs you (the owner's inbox)."""
from lib import *
from lib import RESILIA_TREE
from b_s4 import voice_row

LIBTABS = ["Characters", "Places", "Products", "Presenters & voices", "Brand kit"]


def libpage(brand, tab, body, counts=None, role="owner", tree=None, right=None, active="cast"):
    counts = counts or {"Characters": 4, "Places": 3, "Products": 2, "Presenters & voices": 7, "Brand kit": None}
    t = "".join(f'<span class="{"on" if n == tab else ""}">{n}{f" <span class=n>{counts.get(n)}</span>" if counts.get(n) is not None else ""}</span>' for n in LIBTABS)
    right = right if right is not None else btn("New character", "primary lg", "plus")
    return rail(brand, tree=tree if tree is not None else (RESILIA_TREE if brand == "Resilia" else []), role=role, active=active) + f'''<main class="main">
      <div class="ptop" style="height:56px"><div class="crumb">{brand} {ic("chevron-right","s12")} <b>Library</b></div><span class="t-sm muted">Only {brand} sees these. They fill in each video’s cast.</span><span class="grow"></span>{right}</div>
      <div class="tabs" style="background:var(--surface);padding:0 24px">{t}<span style="flex:1"></span><div class="input" style="height:30px;width:220px;align-self:center">{ic("search","s14")}Search</div></div>
      <div style="padding:20px 24px;overflow:hidden;flex:1">{body}</div></main>'''


def lcard(img, name, sub, tag="", sel=False, w=200, h=266, arch=False):
    tg = f'<span class="tag n">{tag}</span>' if tag else ""
    return f'''<div class="col g2" style="width:{w}px;{"opacity:.6" if arch else ""}">{media(img, w, h, cls="sel" if sel else "")}<div class="col g1"><div class="row g2"><span class="w6">{name}</span><span class="grow"></span>{tg}</div><span class="t-xs muted">{sub}</span></div></div>'''


CHARS = [("still_ugc_still", "Mark", "UGC presenter · used in 6 videos", "Uploaded"), ("still_hostA", "Dr. Pickle", "Presenter · used in 31 videos", ""),
         ("skit_3", "Dana", "Used in 2 videos", "Uploaded"), ("skit_2", "Tom", "Used in 1 video", "")]


def s8_chars(role="owner", arch=False):
    cards = "".join(lcard(i, n, s, t) for i, n, s, t in CHARS)
    if arch:
        cards += lcard("drp_4", "Old Dr. Pickle v1", "Archived 20 Oct · kept for old videos", "Archived", arch=True)
    note = '<span class="t-sm muted">Editors can add and edit characters here too.</span>' if role == "editor" else ""
    return libpage("Resilia", "Characters", f'<div class="row g2" style="margin-bottom:16px"><label class="row g2 t-sm"><span class="check{" on" if arch else ""}">{ic("check","s12") if arch else ""}</span>Show archived</label><span class="grow"></span>{note}</div><div class="row g5 wrap start">{cards}</div>', role=role)


def s8_empty():
    body = f'''<div class="col center g3" style="height:640px;text-align:center"><div class="row g2">{empty_media(90,120)}{empty_media(90,120)}{empty_media(90,120)}</div>
      <span class="t-xl">No characters in Resilia yet</span><span class="t-md muted" style="max-width:460px">Add the people who recur in Resilia’s videos. The director casts them without asking, and every shot keeps the same face.</span>
      <div class="row g2">{btn("Upload a photo", "primary lg", "upload")}{btn("Make one", "lg", "wand-sparkles", "up to $0.08")}</div></div>'''
    return libpage("Resilia", "Characters", body, right=btn("New character", "lg", "plus"), counts={"Characters": 0, "Places": 0, "Products": 0, "Presenters & voices": 0, "Brand kit": None}, tree=[(0, "unsorted", "Unsorted", {"cnt": "0"})])


def s8_item():
    vers = "".join(f'<div class="col g1">{media(i, 70, 94, tag=False, cls="sel" if n == 0 else "")}<span class="t-xs {"w6" if n == 0 else "muted"}">{v}</span></div>' for n, (i, v) in enumerate([("still_ugc_still", "v3 · in use"), ("ugc_2", "v2"), ("ugct_1", "v1")]))
    used = "".join(f'<div class="lrow">{media(i,22,39,tag=False)}<span class="grow w5">{t}</span>{status(k,s)}<span class="t-sm muted" style="width:80px">{d}</span></div>' for i, t, k, s, d in [("ugc_1", "Bloated after pizza", "ok", "Done", "3 Nov"), ("ugc_3", "Gym guy gut", "ok", "Done", "1 Nov"), ("ugc_5", "Date-night bloat", "ok", "Done", "30 Oct")])
    body = f'''<div class="row g8 start"><div class="col g3">{media("still_ugc_still", 300, 400)}<div class="row g2">{vers}</div></div>
      <div class="col g5 grow" style="max-width:640px"><div class="col g1"><div class="row g3"><span class="t-2xl">Mark</span>{status("ok","In use")}<span class="grow"></span>{btn("Change this…","","pencil","up to $0.08")}{btn("Archive","","archive")}</div><span class="t-md muted">UGC presenter · late 40s, tired, warm · navy polo</span></div>
        <div class="kv"><span class="k">Came from</span><span>Uploaded by Reed, 28 Oct (a photo from a shoot)</span><span class="k">Voice</span><span>Roger · relaxed · <span class="accent-t">Play</span></span><span class="k">Place</span><span>Mark’s kitchen</span><span class="k">Rules</span><span>Always the navy polo. No hats.</span></div>
        <div class="col g2"><span class="t-sm w6">Used in 6 videos</span><div class="list">{used}<div class="lrow t-sm muted">+ 3 more</div></div></div></div></div>'''
    return libpage("Resilia", "Characters", body, right=btn("Back to characters", "", "arrow-left"))


def s8_voices():
    pres = "".join(lcard(i, n, s, w=150, h=200) for i, n, s in [("still_hostA", "Dr. Pickle", "Corner over B-roll · P-Video"), ("still_ugc_still", "Mark", "UGC still · HeyGen"), ("still_hostB", "Dr. Ray", "Green-screen talker")])
    voices = voice_row("Dr. Pickle (cloned)", "Deep, fixed · cloned 3 Nov · MiniMax") + voice_row("Roger", "Relaxed, mid · Mark · ElevenLabs") + voice_row("Sarah", "Warm narrator · ElevenLabs") + voice_row("Dana", "Described: “late 30s, dry, quick”")
    body = f'''<div class="row g8 start"><div class="col g3"><div class="row g2"><span class="t-lg">Presenters</span></div><div class="row g4 start">{pres}</div></div>
      <div class="col g3 grow"><div class="row g2"><span class="t-lg">Voices</span><span class="grow"></span>{btn("Clone a voice","","upload","$3.00 once")}</div><div class="col g2">{voices}</div>
      <span class="t-xs muted">Samples play free. A cloned voice is used only for Resilia.</span></div></div>'''
    return libpage("Resilia", "Presenters & voices", body, right=btn("New presenter", "primary lg", "plus"))


def s8_kit():
    screens = "".join(f'<div class="col g1">{media(i, 96, 190, tag=False)}<span class="t-xs muted">{n}</span></div>' for i, n in [("fomo_home", "Home"), ("fomo_home-rich", "Home, rich"), ("fomo_token-up", "Token up")])
    sw = "".join(f'<div class="col g1"><div style="width:44px;height:44px;border-radius:8px;background:{c};border:1px solid var(--border)"></div><span class="t-xs muted">{c}</span></div>' for c in ["#000000", "#ffffff", "#2dd36f", "#7c5cff"])
    body = f'''<div class="row g8 start"><div class="col g5" style="width:520px">
        <div class="col g2"><span class="t-sm w6">Logo</span><div class="row g3">{media("fomo_logo", 72, 72, tag=False)}{btn("Change")}</div></div>
        <div class="col g2"><span class="t-sm w6">Colours</span><div class="row g3">{sw}</div></div>
        <div class="col g2"><span class="t-sm w6">End line</span><div class="input" style="color:var(--text)">Want to trade like me? Download fomo through the link in my bio.</div><span class="t-xs muted">The default ending. The director may adapt the words per video.</span></div>
        <div class="col g2"><span class="t-sm w6">Tone and rules</span><div class="list" style="padding:10px 12px"><span class="t-sm">fomo only in a positive light: wins on fomo, losses on plain apps. Always the real fomo UI; coins and numbers can be made up. Loading screens are dark with the fomo eyes and logo.</span></div></div></div>
      <div class="col g3 grow"><div class="row g2"><span class="t-sm w6">App screens</span><span class="t-xs muted">3 of 10 shown · shown as given; coin, numbers and chart follow the story · <span class="accent-t">Show all</span></span><span class="grow"></span>{btn("Add","","plus")}</div><div class="row g3">{screens}{empty_media(96,190)}</div></div></div>'''
    return libpage("fomo", "Brand kit", body, counts={"Characters": 1, "Places": 0, "Products": 0, "Presenters & voices": 0, "Brand kit": None}, tree=[(0, "folder", "House remakes", {"cnt": "21"}), (0, "folder", "Movies", {"cnt": "2"}), (0, "unsorted", "Unsorted", {"cnt": "4"})], right=btn("Save changes", "primary lg"), active="brand")


def s8_products():
    body = f'''<div class="row g5 start">{lcard("ip_bag_pb", "Peanut butter bag", "Main text must read right: Iron Paws, the claim, the flavour", "Real photo", w=220, h=300)}
      {f'<div class="col g2" style="width:220px">{empty_media(220,300,"empty",'<span class="play" style="color:var(--text-muted);flex-direction:column;gap:6px">'+ic("upload","s20")+'<span class="t-sm">Chicken bag</span></span>')}<div class="col g1"><span class="w6">Chicken bag</span><span class="t-xs muted">No photo yet. The director asks for it when a video needs it.</span></div></div>'}</div>'''
    return libpage("Iron Paws", "Products", body, counts={"Characters": 2, "Places": 1, "Products": 2, "Presenters & voices": 1, "Brand kit": None}, tree=[(0, "folder", "Pitbull series", {"cnt": "6"}), (0, "unsorted", "Unsorted", {"cnt": "1"})], right=btn("New product", "primary lg", "plus"))


def s8_making():
    gen = f'''<div class="col g3" style="width:620px"><span class="t-lg">New character</span>
      <div class="row g3 start">{"".join(empty_media(140, 190, "working") for _ in range(3))}</div>
      <span class="t-sm muted row g2">{ic("loader-circle","s14")}Drawing a front, side and back sheet from your description · up to $0.08 · about 30 s</span>
      <div class="input" style="color:var(--text)">“Woman, late 30s, glasses, cardigan, tired but kind”</div></div>'''
    imp = f'''<div class="col g3" style="width:560px"><span class="t-lg">Import from the brand’s website</span>
      <div class="input" style="color:var(--text)">{ic("globe","s14")}resilia-gut.com</div>
      <div class="list">{"".join(f'<div class="lrow"><span class="step"><span class="ic {s}">{ic("check","s12") if s=="done" else (ic("loader-circle","s12") if s=="now" else "")}</span></span><span class="grow">{t}</span><span class="t-xs muted">{d}</span></div>' for s, t, d in [("done","Logo","found"),("done","Colours","3 found"),("now","Products","reading 4 pages"),("todo","Tone of voice",""),("todo","End line","")])}</div>
      <span class="t-xs muted">Free. You approve each item before it’s saved to Resilia.</span></div>'''
    return libpage("Resilia", "Characters", f'<div class="row g8 start">{gen}{imp}</div>', right=btn("New character", "primary lg", "plus"))


board("S8-01", "Brand library", "Characters · owner", s8_chars())
board("S8-02", "Brand library", "An empty brand", s8_empty())
board("S8-03", "Brand library", "One item open · versions, where it’s used", s8_item())
board("S8-04", "Brand library", "Presenters and voices", s8_voices())
board("S8-05", "Brand library", "Brand kit (fomo: real logo and screens)", s8_kit())
board("S8-06", "Brand library", "Products (Iron Paws: real bag)", s8_products())
board("S8-07", "Brand library", "Generating a new character · importing from a website", s8_making())
board("S8-08", "Brand library", "Editor’s view · archived shown", s8_chars("editor", True))


# ---------- S9 Needs you ----------
def s9():
    def item(brand, idea, img, body, actions, when):
        return f'''<div class="list" style="padding:14px 16px;display:flex;gap:14px;align-items:flex-start">{media(img, 54, 96, tag=False)}
          <div class="col g2 grow"><div class="row g2 t-sm"><span class="w6">{idea}</span><span class="muted">· {brand}</span><span class="grow"></span><span class="t-xs muted">{when}</span></div>{body}<div class="row g2 wrap">{actions}</div></div></div>'''
    q = item("Resilia", "Bloated after pizza", "ugc_1", '<span class="t-md w6">Who should be the presenter?</span><div class="row g2">' + media("still_ugc_still", 64, 86, tag=False, cls="sel") + media("skit_1", 64, 86, tag=False) + '</div>',
             btn("Use Mark", "", "check") + btn("Open the chat", "", "message-square"), "12 min")
    b = item("Resilia", "Why IPAs hit harder", "drp_3", '<span class="t-md w6">Redo clips 9 and 12 · $1.54 past the budget</span><span class="t-sm muted">Kel’s video. $16.30 spent plus up to $2.10 makes up to $18.40; budget $16.86. Lips late on two lines.</span>',
             btn("Approve · up to $2.10 more", "primary", "check") + btn("Decline") + btn("Open the chat", "", "message-square"), "31 min")
    h = item("Resilia", "Gut check (Kel’s send)", "sk2", '<span class="t-md w6">Kel’s new video · up to $16.40</span><span class="t-sm muted">Pasted script, Skeleton style, 45 s. Nothing is spent until you approve.</span>',
             btn("Approve and start", "", "check") + btn("Decline") + btn("Read the script", "", "file-text"), "1 h")
    s = item("Resilia", "Night-time bloat", "pk3", '<span class="t-md w6">Clip 4 couldn’t be made</span><span class="t-sm muted">It’s 115 s; the model makes 12 s. Split it at the sentence breaks (free).</span>',
             btn("Split it · free", "", "check") + btn("Open the chat", "", "message-square"), "2 h")
    body = f'''<div style="padding:24px;display:flex;justify-content:center"><div class="col g4" style="width:860px">
      <div class="row g3"><span class="t-2xl">Needs you</span><span class="badge need">4</span><span class="grow"></span><div class="seg"><span class="on">All brands</span><span>Resilia 4</span><span>fomo 0</span></div></div>
      <span class="t-sm muted">Questions from the director, budget OKs and stuck videos, across every brand. Answer here or in the video’s chat; it’s the same answer.</span>
      <span class="t-sm w6" style="margin-top:4px">Questions</span>{q}
      <span class="t-sm w6">Money</span>{b}{h}
      <span class="t-sm w6">Stuck</span>{s}</div></div>'''
    return rail(tree=RESILIA_TREE, active="needs", needs=4) + f'<main class="main"><div class="ptop"><div class="crumb"><b>Needs you</b></div></div>{body}</main>'


board("S9-01", "Needs you", "Owner’s inbox · questions, money, stuck", s9())
