"""S5 cast and presenter; S6 clips for long videos. The preview panel widens; the chat stays beside it."""
from lib import *
from b_s3 import chat_col, progress, progress_states, all_done, ME, KEL, MORE, T, CRUMB

FOMO_TREE = [(0, "folderopen", "House remakes", {"cnt": "21"}), (1, "idea", "Three dimes to a penthouse", {"dot": "need", "on": True}), (1, "idea", "Laughed at in a junk car", {"dot": "ok"}),
             (1, "idea", "Dumped at the altar", {"dot": "ok"}), (0, "folder", "Movies", {"cnt": "2"}), (0, "folder", "Week of 3 Nov", {"cnt": "8"}), (0, "unsorted", "Unsorted", {"cnt": "4"})]
FCRUMB = f'fomo {ic("chevron-right","s12")} House remakes'


def short_chat(thread, title="Three dimes to a penthouse", state=None, price=None, locks=None, crumb=FCRUMB, role="owner"):
    state = state or status("need", "Needs you")
    price = price or price_owner("up to $19.40", "$1.10 spent ·")
    locks = locks or default_locks(fmt="Dialogue", sty="House", castn="Marcus +2", cast=False, length="about 65 s", more="+2")
    return chat_col(title, state, price, thread, locks=locks, crumb=crumb, narrow=True, right=MORE)


def role_card(img, name, role, src, state_html, actions="", note="", cls="", imgs=None):
    pic = imgs if imgs else (media(img, 88, 118, tag=False) if img else empty_media(88, 118, "empty", f'<span class="play" style="color:var(--warning)">{ic("user-round","s20")}</span>'))
    n = f'<span class="t-xs muted">{note}</span>' if note else ""
    return f'''<div class="role {cls}">{pic}<div class="col g2 grow"><div class="row g2"><span class="w6 t-md">{name}</span><span class="t-sm muted">{role}</span><span class="grow"></span>{state_html}</div>
      <span class="t-sm muted">{src}</span>{n}<div class="row g2 wrap">{actions}</div></div></div>'''


# ---------- S5 ----------
def s5_cast(role="owner"):
    owner = role == "owner"
    gen_price = "$0.08" if owner else "1 credit"
    cards = [
        role_card("house_marcus_rain", "Marcus", "Main character · in 9 of 9 clips", "Look made for this video · not in the library", status("ok", "Approved"),
                  btn("Change this…", "", "pencil") + btn("Lock", "", "lock") + btn("Outfit for this video", "", "sliders-horizontal")),
        role_card("sheet_gothgf", "Jade", "Girlfriend · in 3 clips", "Saved in fomo: “Goth GF” v4", status("ok", "Locked"), btn("Unlock", "", "lock"), cls=""),
        role_card(None, "Chase", "Rival · in 4 clips", "No sheet yet. Clips 2–4 wait for him.", status("need", "Needs a look"),
                  btn("Pick from fomo’s cast", "primary", "users") + btn("Upload", "", "upload") + btn("Make a look", "", "wand-sparkles", gen_price), cls="need"),
        role_card(None, "Mom · Mom (kitchen)", "In 1 clip each", "These may be the same person.", status("need", "Check"),
                  btn("Merge into Mom", "", "copy") + btn("They’re different"), imgs=f'<div class="row g1">{media("skit_3",42,118,tag=False)}{media("skit_1",42,118,tag=False)}</div>'),
    ]
    body = f'''<div class="row between"><span class="t-lg">Cast</span><span class="t-sm muted">4 roles · background people are drawn as part of each scene</span></div>
      <div class="col g3">{"".join(cards)}</div>
      <div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("lock","s14 muted")}<span>Locked looks are used as they are in every shot. The sheet sets the face{", and the outfit unless this video sets its own" if True else ""}.</span></div>'''
    thread = f"""{m_me('Remake the three-dimes reel for fomo, House style. Same words.', '09:02', *(ME if owner else KEL))}
      {m_dir('<p>Cast read: 4 roles. Jade is saved in fomo, so she’s locked in. Marcus got a look for this video; it’s in the Cast tab.</p>', '09:05')}
      {m_dir('<p>Chase has no look yet, so clips 2–4 wait. Everything else carries on. Pick him from fomo’s cast, upload one, or I make one.</p>', '09:06')}"""
    return rail("fomo", tree=FOMO_TREE, role=role) + short_chat(thread, price=price_owner("up to $19.40", "$1.10 spent ·") if owner else price_editor("up to 189 credits", "11 credits ·")) + panel("Cast", body, [("Cut", None), ("Clips", "9"), ("Cast", "4"), ("Plan", None), ("Script", None)])


def s5_presenter():
    look = [("drp_2", "In a corner over the B-roll", "Dr. Pickle, UGC split"), ("still_host_waist", "Full green-screen talker", "keyed over B-roll"), ("ugc_2", "Still talking head", "UGC from one photo")]
    ap = "".join(f'<div class="col g1" style="width:150px">{media(i, 150, 200, tag=False, cls="sel" if n == 0 else "")}<span class="t-sm w6">{t}</span><span class="t-xs muted">{s}</span></div>' for n, (i, t, s) in enumerate(look))
    from b_s4 import voice_row
    body = f'''<div class="row between"><span class="t-lg">Presenter</span><span class="t-sm muted">Talks over the B-roll for the whole video</span></div>
      <div class="row g5 start"><div class="col g2">{media("still_hostA", 150, 266)}<span class="t-xs muted">Dr. Pickle · saved in Resilia</span></div>
        <div class="col g3 grow">
          <div class="kv"><span class="k">Avatar</span><span>Dr. Pickle still · <span class="accent-t">Change</span></span>
            <span class="k">Made with</span><span>P-Video lip-sync, in pieces under 12 s</span>
            <span class="k">Voice</span><span>His cloned voice · MiniMax · <span class="accent-t">Change</span></span></div>
          <div class="col g2">{voice_row("Dr. Pickle (cloned)", "Deep, fixed · MiniMax clone", True)}{voice_row("Roger", "Relaxed · UGC")}</div>
          <span class="t-xs muted">Voices play here free. A new clone costs $3.00 once.</span></div></div>
      <div class="col g2"><span class="t-sm w6">How the presenter appears</span><div class="row g3 start">{ap}</div></div>
      <div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("circle-question-mark","s14 muted")}<span>UGC presenters are made with HeyGen from one still and a realistic voice with room sound. Dr. Pickle uses his cloned voice.</span></div>'''
    thread = f"""{m_dir('<p>Dr. Pickle and his cloned voice are saved in Resilia, so I used them. He sits bottom-right; I’ll switch sides when the B-roll needs the space.</p>', '10:04')}"""
    from lib import RESILIA_TREE
    return rail(tree=RESILIA_TREE) + chat_col(T, status("work", "Working"), price_owner("up to $16.86", "$2.40 spent ·"), thread, narrow=True,
                                               locks=default_locks(more="+2")) + panel("Cast", body)


def s5_states():
    W = 640
    cells = [
        ("Generating a look", role_card(None, "Chase", "Rival", "Drawing a front, side and back sheet · up to $0.08 · about 30 s", status("work", "Drawing"), btn("Cancel"),
                                        imgs=f'<div class="row g1">{empty_media(42,118,"working")}{empty_media(42,118,"working")}{empty_media(42,118,"working")}</div>')),
        ("Approved", role_card("house_marcus_rain", "Marcus", "Main character", "Look made for this video · approved 09:10", status("ok", "Approved"), btn("Change this…", "", "pencil") + btn("Lock", "", "lock"))),
        ("Locked", role_card("sheet_gothgf", "Jade", "Girlfriend", "Saved in fomo · used as is in every shot", status("ok", "Locked"), btn("Unlock", "", "lock"))),
        ("These may be the same person", role_card(None, "Mom · Mom (kitchen)", "", "One person is never two roles. Merge them, or say they’re different for this video.", status("need", "Check"),
                                                   btn("Merge into Mom", "", "copy") + btn("They’re different"), imgs=f'<div class="row g1">{media("skit_3",42,118,tag=False)}{media("skit_1",42,118,tag=False)}</div>')),
        ("Outfit just for this video", role_card("house_marcus_rain", "Marcus", "Main character", "Outfit for this video: rain-soaked green hoodie, grey joggers. The sheet still sets the face.", status("ok", "Approved"), btn("Change outfit", "", "pencil") + btn("Use the sheet’s outfit"))),
        ("No sheet yet: Clips waits, one press away", role_card(None, "Chase", "Rival · in 4 clips", "Clips 2–4 can’t start without him.", status("need", "Needs a look"),
                                                                btn("Pick from fomo’s cast", "primary", "users") + btn("Upload", "", "upload") + btn("Make a look", "", "wand-sparkles", "$0.08"), cls="need")),
        ("Editor’s view", role_card("house_marcus_rain", "Marcus", "Main character", "Look made for this video", status("ok", "Approved"), btn("Change this…", "", "pencil", "1 credit"))),
        ("A brand with no saved characters", f'<div class="role" style="flex-direction:column;align-items:flex-start"><span class="w6">Resilia has no saved characters yet</span><span class="t-sm muted">The director prepares the characters and places. Review them together, request any changes, then approve the cast and places to continue. To reuse a person in every video, add them in Cast &amp; places.</span><div class="row g2">{btn("Open Cast & places","","users")}</div></div>'),
    ]
    cols = [cells[0::2], cells[1::2]]
    c = "".join(f'<div class="col g6" style="width:{W}px">{"".join(f"<div class=\'col g2\'><span class=\'t-sm w6\'>{a}</span>{b}</div>" for a, b in col)}</div>' for col in cols)
    return f'<div class="col g2" style="margin-bottom:24px"><span class="t-2xl">Cast: role states</span><span class="t-sm muted">Each role shows its picture, where it came from, its state and the one press that moves it on.</span></div><div class="row g8 start">{c}</div>'


board("S5-01", "Cast and presenter", "Cast · owner · one role needs a look", s5_cast("owner"))
board("S5-02", "Cast and presenter", "Presenter: avatar, voice, how it appears", s5_presenter())
board("S5-03", "Cast and presenter", "Role states sheet", s5_states(), "s", h=1080)
board("S5-04", "Cast and presenter", "Cast · editor (credits)", s5_cast("editor"))


# ---------- S6 clips ----------
def clip_row(n, img, title, dur, model, st_html, sel=False, extra=""):
    pic = media(img, 36, 64, tag=False) if img else empty_media(36, 64)
    return f'<div class="lrow{" sel" if sel else ""}" style="padding:6px 10px">{pic}<div class="col grow" style="min-width:0"><div class="row g2"><span class="w6 t-sm">Clip {n}</span><span class="t-xs muted">{dur} · {model}</span></div><span class="t-xs muted ell">{title}</span>{extra}</div>{st_html}</div>'


def clip_detail(owner=True, flagged=False):
    p = (lambda o, e: o if owner else e)
    takes = [("pk1pv", "Take 1", "Dropped: the eyes landed on the stomach", False), ("pk1", "Take 2 · in the cut", "Remade on Seedance 2.0", True), (None, "", "", False)]
    tk = "".join(f'<div class="take{" best" if b else ""}" style="width:130px">{media(i, 130, 231, play=True, dur="4 s") if i else ""}<span class="t-sm w6">{t}</span><span class="t-xs muted">{r}</span></div>' for i, t, r, b in takes if i)
    found = ""
    if flagged:
        found = f'''<div class="row g2 start t-sm" style="padding:10px 12px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px">{ic("eye","s14")}<div><b class="w6">What I found watching take 1:</b> cartoon eyes landed on the stomach at 0:02 (Dr. Pickle’s guide keeps faces off organs). The sound was fine.<br><b class="w6">What I did:</b> remade it on Seedance 2.0 with “no face on the organs” in the prompt. {p("$0.32", "3 credits")}.</div></div>'''
    return f'''<div class="col g4"><div class="row g2"><span class="t-lg">Clip 7</span><span class="t-sm muted">Scene 2 · What beer does · 4 s · B-roll</span><span class="grow"></span>{status("ok","In the cut")}</div>
      {found}
      <div class="row g3 start">{tk}</div><div class="col g2"><div class="kv" style="grid-template-columns:96px 1fr"><span class="k">Model</span><span>Seedance 2.0 · 480p</span><span class="k">Why</span><span class="muted">Dr. Pickle’s default for B-roll. Silent: B-roll gets sound effects only when asked</span>
            <span class="k">Words over it</span><span>“Every pint sits there and ferments.”</span>
            <span class="k">Cost</span><span>{p("$0.64 (2 takes)", "6 credits (2 takes)")}</span></div></div></div>
      <div class="col g1"><div class="row between"><span class="t-xs w6 muted">The director’s prompt</span><span class="t-xs accent-t w5">Edit</span></div>
        <div class="prompt">Glossy 3D see-through male torso, beer pouring down the throat into a swelling, gurgling stomach, warm amber light, slow push in. No face on the organs. No one speaks. No music.</div></div>
      <div class="row g2 wrap">{btn("Change this…", "", "pencil", p("$0.32","3 credits"))}{btn("Another take", "", "refresh-cw", p("$0.32","3 credits"))}{btn("Add sound effects", "", "volume-2", p("$0.01","under 1 credit"))}{btn("Swap B-roll", "", "arrow-right-left")}{btn("Download", "", "download")}</div></div>'''


def s6_long():
    from lib import SCENES
    frames = ["skit_1", "skit_2", "skit_3", "ugc_4", "ugcb_5", "ugc_2"]
    scenes = [("1. The eviction notice", 9, "9 of 9"), ("2. Laughed out of the bank", 11, "11 of 11"), ("3. Night shift", 8, "8 of 8"), ("4. The mentor’s diner", 12, "12 of 12"), ("5. First trade", 10, "7 of 10")]
    rows = []
    for si, (nm, n, d) in enumerate(scenes):
        open_ = si == 4
        rows.append(f'<div class="lrow hd" style="padding:8px 10px">{ic("chevron-down" if open_ else "chevron-right","s12")}<span class="w6" style="color:var(--text)">{nm}</span><span class="grow"></span><span class="num">{d}</span></div>')
        if open_:
            for j in range(n):
                k = si * 10 + j
                if j < 7:
                    stt = status("ok", "In the cut") if j != 3 else status("need", "Flagged")
                    rows.append(clip_row(41 + j, frames[(k) % 6], ["Marcus opens the app", "Close on the chart", "His face lit by the screen", "Dana leans in", "The first win", "He exhales", "Dana grins"][j], "6 s", "Omni 720p", stt, sel=(j == 3)))
                else:
                    rows.append(clip_row(41 + j, None, ["He hits Buy", "The balance climbs", "Hard cut to morning"][j - 7], "6 s", "Omni 720p", status("work", "Making")))
    body = f'''<div class="row g3"><div class="seg"><span class="on">All 118</span><span>Needs you 1</span><span>Flagged 3</span><span>Redone 4</span></div><div class="input" style="height:30px;width:200px">{ic("search","s14")}Find a clip or a line</div><span class="grow"></span><span class="t-sm muted">47 of 118 made</span></div>
      <div class="row g4 start" style="flex:1;min-height:0"><div class="list" style="width:330px;flex:none;overflow:hidden;max-height:740px">{"".join(rows)}</div>
      <div class="col g3 grow"><div class="row g2"><span class="t-lg">Clip 44</span><span class="t-sm muted">Scene 5 · Dana leans in · 6 s · Omni 720p</span><span class="grow"></span>{status("need","Flagged")}</div>
        <div class="row g2 start t-sm" style="padding:10px 12px;background:var(--warning-soft);color:var(--warning);border-radius:8px">{ic("eye","s14")}<div><b class="w6">Dana’s voice drifts:</b> it sounds higher than in scene 4. Omni can’t take a voice sample, so I described her voice the same way in both prompts. Remake it (up to $0.90), or keep it?</div></div>
        <div class="row g3 start">{media("skit_3",150,266,play=True,dur="6 s")}{media("skit_1",150,266,play=True,dur="6 s")}</div><span class="t-xs muted">Take 1 (scene 4, for comparison) · Take 2 (this clip)</span><div class="col g1"><span class="t-xs w6 muted">Words in this clip</span><span class="t-sm">DANA: “Wait… is that real?”</span></div><div class="row g2 wrap">{btn("Remake it","primary","refresh-cw","up to $0.90")}{btn("Keep it")}</div></div></div>'''
    tree = [(0, "folderopen", "Movies", {"cnt": "2"}), (1, "idea", "The landlord (7 min)", {"dot": "work", "on": True}), (0, "folder", "House remakes", {"cnt": "21"}), (0, "unsorted", "Unsorted", {"cnt": "4"})]
    thread = f"""{m_dir('<p>47 of 118 made. One flag: Dana’s voice drifts in clip 44. Details in Clips.</p>', '09:46')}"""
    return rail("fomo", tree=tree) + chat_col("The landlord (7 min)", status("work", "Working"), price_owner("up to $96.40", "$41.20 ·"), thread, narrow=True,
                                               locks=default_locks(fmt="Dialogue", sty="Movie", castn="Marcus +5", length="7 min", more="+2"), crumb=f'fomo {ic("chevron-right","s12")} Movies') + panel("Clips", body, [("Cut", None), ("Clips", "118"), ("Cast", "6"), ("Plan", None), ("Script", None)])


def s6_short():
    imgs = ["ugc_1", "ugcb_4", "ug1", "ugc_3", "ug2", "ugc_5"]
    titles = ["Mark to camera: “Pizza night used to wreck me”", "On the couch, holding his belly", "Coffee, again", "Mark: “Then I tried this”", "The capsule, close", "Mark: “Link in my bio”"]
    sts = [status("ok", "In the cut"), status("ok", "In the cut"), status("ok", "Redone"), status("ok", "In the cut"), status("ok", "In the cut"), status("ok", "In the cut")]
    grid = "".join(f'<div class="col g2" style="width:150px">{media(i,150,266,play=True,dur=d)}<div class="row g2"><span class="t-sm w6">Clip {n+1}</span><span class="grow"></span>{s}</div><span class="t-xs muted">{t}</span></div>' for n, (i, t, s, d) in enumerate(zip(imgs, titles, sts, ["6 s", "4 s", "3 s", "7 s", "3 s", "5 s"])))
    body = f'<div class="row between"><span class="t-lg">Clips</span><span class="t-sm muted">6 clips · 28 s · all in the cut</span></div><div class="row g4 wrap start">{grid}</div>'
    tree = resilia_tree("Bloated after pizza", {"Bloated after pizza": "ok"})
    thread = f"""{m_dir('<p>Delivered. Clip 3 was redone: the coffee pour froze for half a second.</p>', '11:52')}"""
    return rail(tree=tree) + chat_col("Bloated after pizza", status("ok", "Delivered"), price_owner("$4.80 of up to $7.40", ""), thread, narrow=True,
                                       locks=default_locks(fmt="Presenter", sty="UGC", castn="Mark", length="28 s", more="+2"), right=MORE) + panel("Clips", body, [("Cut", None), ("Clips", "6"), ("Cast", "1"), ("Plan", None), ("Script", None)])


def s6_open(flagged=True, owner=True):
    from lib import SCENES
    st = all_done()
    rows = []
    n = 0
    for si, (nm, frames) in enumerate(SCENES[:3]):
        rows.append(f'<div class="lrow hd" style="padding:8px 10px">{ic("chevron-down","s12")}<span class="w6" style="color:var(--text)">Scene {si+1} · {nm}</span><span class="grow"></span><span>{len(frames)}</span></div>')
        for fi, f in enumerate(frames):
            n += 1
            sel = (n == 7)
            stt = status("ok", "Redone") if sel else status("ok", "In the cut")
            rows.append(clip_row(n, f, ["Glowing spine", "Dr. Pickle points", "Heart close-up", "Dr. Pickle points again", "Skeleton on the couch", "The stomach swells", "Beer down the throat", "Gut lining", "Bloat glows green", "Dr. Pickle, arms crossed", "Close on the gut"][min(n - 1, 10)], "4 s", "Seedance 2.0", stt, sel=sel))
    body = f'''<div class="row g3"><div class="seg"><span class="on">All 24</span><span>Needs you 0</span><span>Flagged 0</span><span>Redone 3</span></div><span class="grow"></span><span class="t-sm muted">Grouped by scene</span></div>
      <div class="row g4 start"><div class="list" style="width:300px;flex:none">{"".join(rows)}</div><div class="grow">{clip_detail(owner, flagged)}</div></div>'''
    RESILIA_TREE = resilia_tree(T, {T: "ok"})
    thread = f"""{m_dir('<p>Here’s the cut. I watched and listened to every take and the whole cut twice.</p><div class="card" style="padding:8px 12px"><span class="t-sm muted">Delivery note · 3 clips redone</span></div>', '10:25')}"""
    return rail(tree=RESILIA_TREE, role="owner" if owner else "editor") + chat_col(T, status("ok", "Delivered"), price_owner("$9.84 of up to $16.86", "") if owner else price_editor("96 of up to 164 credits", ""), thread, narrow=True,
                                                                                    locks=default_locks(more="+2"), right=MORE) + panel("Clips", body)


def s6_states():
    cells = [
        ("Making", clip_row(15, "drp_4", "Dr. Pickle points at the clock", "6 s", "P-Video", status("work", "Making · about 3 min"), extra='<div class="prog" style="width:160px;margin-top:4px"><i style="width:45%"></i></div><span class="t-xs muted">The still is ready; the take is being made</span>')),
        ("Watched and redone by the director", clip_row(7, "pk1", "Beer down the throat", "4 s", "Seedance 2.0", status("ok", "Redone"), extra='<span class="t-xs accent-t">Eyes landed on the stomach → remade</span>')),
        ("Flagged, needs you", clip_row(44, "skit_3", "Dana leans in", "6 s", "Omni", status("need", "Flagged"), extra='<span class="t-xs warn-t">Her voice drifts · remake or keep</span>')),
        ("A take failed (nothing charged)", clip_row(12, "drp_6", "The stomach swells", "4 s", "Seedance 2.0", status("bad", "Failed"), extra=f'<span class="t-xs bad-t">The service was busy. Nothing was charged.</span><div style="margin-top:6px">{btn("Try again · free","","refresh-cw")}</div>')),
        ("Waiting for the owner", clip_row(9, "drp_3", "Spine on fire", "4 s", "P-Video", status("wait", "Waiting for the owner"), extra='<span class="t-xs warn-t">Redo past the budget · 8 credits</span>')),
        ("Words in the picture, found and fixed", clip_row(20, "hostA_talk", "Dr. Pickle: “Link in my bio”", "5 s", "P-Video", status("ok", "Redone"), extra='<span class="t-xs accent-t">Garbled words burned in → remade with “no text”</span>')),
    ]
    c = "".join(f'<div class="col g2" style="width:600px"><span class="t-sm w6">{a}</span><div class="list">{b}</div></div>' for a, b in cells)
    return f'<div class="col g2" style="margin-bottom:24px"><span class="t-2xl">Clips: row states</span><span class="t-sm muted">Every clip says what happened to it in words, and the press that moves it on shows its price. Editors see credits.</span></div><div class="row g8 wrap start" style="row-gap:24px">{c}</div>'


board("S6-01", "Clips", "A short video · 6 clips", s6_short())
board("S6-02", "Clips", "One clip open · takes, prompt, model and why, actions", s6_open(False))
board("S6-03", "Clips", "Found by the director’s watch · what it found and redid", s6_open(True))
board("S6-04", "Clips", "A long video · 118 clips grouped by scene · when Movie is on", s6_long())
board("S6-05", "Clips", "Row states sheet: making, redone, flagged, failed, waiting, text found", s6_states(), "s", h=620)
board("S6-06", "Clips", "One clip open · editor (credits)", s6_open(True, False))
