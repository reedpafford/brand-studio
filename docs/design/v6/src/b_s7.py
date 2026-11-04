"""S7: the cut editor. Trim, re-time to the words, presenter over B-roll, swap B-roll, sound effects, duck the music."""
from lib import *
from lib import RESILIA_TREE, SCENES
from b_s3 import chat_col, ME, KEL, MORE, T

PX = 10.6  # px per second (58 s fills the 620 px lane)
BROLL = [("drp_1", 0, 2.6), ("drp_3", 2.6, 5.2), ("pk1", 5.2, 8.4), ("sd1", 8.4, 11.6), ("drp_6", 11.6, 14.0), ("pk1pv", 14.0, 18.0), ("sd3", 18.0, 21.4), ("sd2", 21.4, 24.8),
         ("drp_5", 24.8, 27.6), ("drp_4", 27.6, 31.2), ("pk3", 31.2, 34.6), ("pk2", 34.6, 38.0), ("pk3pv", 38.0, 41.0), ("ug2", 41.0, 44.6), ("drp_2", 44.6, 48.0), ("ug1", 48.0, 52.0), ("drp_5", 52.0, 55.4), ("drp_1", 55.4, 58.0)]
SFX = [("gurgle", 15.0, 17.2), ("burp", 22.0, 23.0), ("clock tick", 28.0, 30.4), ("pop", 41.2, 42.0)]


def seg(cls, a, b, label="", extra_cls="", inner=""):
    return f'<div class="seg2 {cls} {extra_cls}" style="left:{a*PX:.0f}px;width:{(b-a)*PX-2:.0f}px">{inner or label}</div>'


def timeline(sel=None, changed=(), dirmarks=(), building=None, music_sel=False, playhead=14.6, dim=False):
    ruler = "".join(f'<span style="position:absolute;left:{s*PX:.0f}px;bottom:2px">0:{s:02d}</span><span style="position:absolute;left:{s*PX:.0f}px;bottom:0;height:5px;width:1px;background:var(--border-strong)"></span>' for s in range(0, 60, 5))
    br = []
    for i, (f, a, b) in enumerate(BROLL):
        if building is not None and a > building:
            br.append(seg("", a, b, extra_cls="", inner="").replace('class="seg2 "', 'class="seg2" style="background:var(--surface-2);border:1px dashed var(--border-strong)"').replace('" style="left', ';left'))
            continue
        x = (" sel" if sel == i else "") + (" dirmark" if i in dirmarks else "")
        imgs = "".join(f'<img src="{src(f)}">' for _ in range(max(1, int((b - a) * PX // 22))))
        br.append(seg("clip", a, b, extra_cls=x.strip(), inner=imgs + ('<span style="position:absolute;inset:0;border:2px solid #d48a12;border-radius:4px"></span>' if i in changed else "")))
    host = [seg("host", 0, 26.0, "Dr. Pickle · bottom right"), seg("host dirmark", 26.0, 41.0, "bottom left (switched)"), seg("host", 41.0, 58.0, "bottom right")]
    if building is not None:
        host = [seg("host", 0, min(building, 26), "Dr. Pickle · bottom right")]
    voice = seg("voice", 0, 58.0, "Dr. Pickle’s voice · “Your gut after the weekend? A brewery with a pulse. Every pint sits there and ferments…”")
    duck = '<svg style="position:absolute;inset:0" width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 614 32"><path d="M0 8 L4 26 L608 26 L614 8" fill="none" stroke="#6a3f9c" stroke-width="1.2" stroke-dasharray="3 2"/></svg>'
    music = seg("music" + (" sel" if music_sel else ""), 0, 58.0, inner=f'<span style="position:relative;z-index:1">Music · “Low synth bed” · much quieter under the voice</span>{duck}')
    sfx = "".join(seg("sfx" + (" dirmark" if n == "gurgle" else ""), a, max(b, a + 5.2), inner=ic("volume-2", "s12") + f'<span style="margin-left:3px">{n}</span>') for n, a, b in SFX)
    ph = f'<div class="playhead" style="left:{132 + playhead*PX:.0f}px"></div>'
    rows = [("Presenter", "user-round", "".join(host)), ("B-roll", "film", "".join(br)), ("Voice", "mic", voice), ("Music", "audio-lines", music), ("Sound effects", "volume-2", sfx)]
    r = "".join(f'<div class="tlrow"><div class="nm">{ic(i,"s14")}{n}</div><div class="lane">{c}</div></div>' for n, i, c in rows)
    if dim:
        ph = ""
    return f'''<div class="tl" style="position:relative;border:1px solid var(--border);border-radius:8px;overflow:hidden;{"opacity:.45;pointer-events:none" if dim else ""}">
      <div class="row" style="height:36px;padding:0 10px;gap:8px;border-bottom:1px solid var(--border)"><span class="iconbtn">{ic("rotate-ccw","s14")}</span><span class="iconbtn" style="transform:scaleX(-1)">{ic("rotate-ccw","s14")}</span>
        <span class="iconbtn">{ic("scissors","s14")}</span><span class="t-xs muted">Split at the playhead</span><span class="grow"></span><span class="t-xs muted">Snap to words</span><span class="check on">{ic("check","s12")}</span><span class="t-xs muted">· 0:14.6 / 0:58.0</span></div>
      <div class="row"><div style="width:132px;flex:none"></div><div class="ruler grow">{ruler}</div></div>{r}{ph}</div>'''


def words(now=13):
    w = "Your gut after the weekend? A brewery with a pulse. Every pint sits there and ferments. That’s not a belly. That’s a science project.".split()
    out = "".join(f'<span class="{"said" if i < now else ("now" if i == now else "later")}">{x}</span>' for i, x in enumerate(w))
    return f'<div class="words">{out}</div>'


def inspector_broll(owner=True, editor=False):
    sfxp = "under 1 credit" if editor else "$0.01"
    swaps = "".join(f'<div class="col g1">{media(i, 64, 114, tag=False, cls="sel" if n == 0 else "")}<span class="t-xs muted">{l}</span></div>' for n, (i, l) in enumerate([("pk1pv", "In the cut"), ("pk1", "Take 1"), ("sd1", "Clip 4"), ("drp_6", "Library")]))
    return f'''<div class="col g3"><div class="row g2"><span class="t-md w6">B-roll · clip 7</span><span class="t-sm muted num">0:14.0 – 0:18.0 · 4.0 s</span></div>
      <div class="col g1"><span class="t-xs w6 muted">Said over it</span><span class="t-sm">“Every pint sits there and ferments.”</span></div>
      <div class="col g2"><span class="t-xs w6 muted">Swap for</span><div class="row g2">{swaps}</div></div>
      <div class="row g2 wrap">{btn("Re-time to the words", "", "clock")}{btn("Trim", "", "scissors")}{btn("Add sound effects", "", "volume-2", sfxp)}{btn("Presenter: hide here", "", "eye")}</div>
      <span class="t-xs muted">Edits in the cut are free. New takes are made in Clips and show their price.</span></div>'''


def inspector_music():
    return f'''<div class="col g3"><div class="row g2"><span class="t-md w6">Music</span><span class="t-sm muted">“Low synth bed” · 0:00 – 0:58</span></div>
      <div class="col g2"><span class="t-xs w6 muted">Under the voice</span>
        <div class="row g3"><span class="t-sm" style="width:70px">Quieter by</span><div class="grow" style="height:4px;background:var(--surface-3);border-radius:2px;position:relative"><i style="position:absolute;left:0;width:62%;height:100%;background:var(--accent);border-radius:2px"></i><i style="position:absolute;left:62%;top:-6px;width:16px;height:16px;border-radius:50%;background:#fff;border:1px solid var(--border-strong);box-shadow:var(--shadow-soft)"></i></div><span class="t-sm" style="width:90px;text-align:right">A lot <span class="muted">(−18 dB)</span></span></div>
        <div class="row g3"><span class="t-sm" style="width:70px">When no one speaks</span><div class="seg"><span>Stay down</span><span class="on">Rise</span></div></div></div>
      <div class="row g2">{btn("Swap the music", "", "arrow-right-left")}{btn("Remove", "", "x")}</div></div>'''


def editor_body(sel=0, changed=(), dirmarks=(), banner="", inspector=None, player_name="pk1pv", building=None, music_sel=False, top_right=None):
    insp = inspector if inspector is not None else inspector_broll()
    top_right = top_right if top_right is not None else btn("Download MP4", "primary", "download")
    return f'''{banner}<div class="row g3"><span class="t-lg">Cut 2</span><span class="t-sm muted">0:58 · 24 clips</span><span class="grow"></span>{top_right}</div>
      <div class="row g5 start"><div class="col g2">{player(player_name, 236, 420, "0:14", "0:58", 25)}</div>
        <div class="col g3 grow"><div class="card" style="padding:12px">{words()}</div><div class="card" style="padding:14px">{insp}</div></div></div>
      {timeline(sel=5 if sel == 0 else sel, changed=changed, dirmarks=dirmarks, building=building, music_sel=music_sel)}'''


def wrap(body, thread, owner=True, state=None, price=None, dot="ok"):
    state = state or status("ok", "Delivered")
    price = price or (price_owner("$9.84 of up to $16.86", "") if owner else price_editor("96 of up to 164 credits", ""))
    return rail(tree=resilia_tree(T, {T: dot}), role="owner" if owner else "editor") + chat_col(T, state, price, thread, narrow=True, right=MORE, locks=default_locks(more="+2"),
                                                                                    comp=composer("Ask the director to edit: “tighten the gaps”…")) + panel("Cut", body, right=f'<div class="seg" style="margin-right:4px"><span>Watch</span><span class="on">{ic("scissors","s14")}Edit</span></div>')


T1 = f"""{m_dir('<p>Here’s the cut. I watched and listened to every take and the whole cut twice.</p><div class="card" style="padding:8px 12px"><span class="t-sm muted">Delivery note · Cut 1</span></div>', '10:25')}"""

# S7-01 ready
board("S7-01", "Cut editor", "Cut ready · a B-roll piece selected", wrap(editor_body(), T1))

# S7-02 a person editing, unsaved changes
b2 = editor_body(changed=(5, 13), inspector=inspector_music(), music_sel=True,
                 top_right=f'<span class="t-sm warn-t row g1">{ic("pencil","s12")}2 changes not in the cut yet</span>{btn("Undo all")}{btn("Make the cut", "primary", "scissors", "free")}')
board("S7-02", "Cut editor", "A person editing · unsaved changes · ducking the music", wrap(b2, T1 + m_me("I’ll swap a couple of B-roll pieces myself.", "10:50", *ME)))

# S7-03 the director editing
ban3 = f'<div class="row g2 t-sm" style="padding:10px 12px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px">{ic("sparkles","s14")}<span><b class="w6">The director is editing:</b> re-timing clips 9 and 13 to the words and adding a gurgle on clip 7. Its edits are marked with a dot.</span><span class="grow"></span><span class="w6">Watch</span></div>'
t3 = T1 + m_me("Tighten it, the middle drags a bit.", "10:41", *ME) + m_dir('<p>Tightening the middle: I’ll pull clips 9 and 13 onto the words (−1.4 s) and switch Dr. Pickle to the left while the gut fills the right. Free; about 1 min.</p><div class="col g1 t-sm"><div class="row g2"><span class="tag new">0:24</span>Clip 9 re-timed <span class="accent-t">Undo</span></div><div class="row g2"><span class="tag new">0:26</span>Presenter switched sides <span class="accent-t">Undo</span></div></div>', "10:41")
b3 = editor_body(dirmarks=(8, 12, 5), banner=ban3, top_right=f'<span class="t-sm muted row g1">{ic("loader-circle","s12")}Editing · you can watch</span>')
board("S7-03", "Cut editor", "The director editing · its edits marked, each with Undo", wrap(b3, t3, state=status("work", "Working · editing the cut"), dot="work"))

# S7-04 building the cut
ban4 = f'<div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("loader-circle","s14 accent-t")}<span>Making the cut: laying Dr. Pickle over the B-roll, music under him · 70%</span></div>'
b4 = f'''{ban4}<div class="row g5 start">{empty_media(236, 420, "working", '<span class="play" style="color:var(--text-muted);flex-direction:column;gap:8px">' + ic("loader-circle","s24") + '<span class="t-sm">Making the cut</span></span>')}
      <div class="col g3 grow"><div class="card" style="padding:12px">{words(0)}</div><span class="t-sm muted">The timeline wakes up when the first cut is ready. Every clip is already in Clips.</span></div></div>{timeline(building=40, dim=True)}'''
board("S7-04", "Cut editor", "Building the first cut", wrap(b4, f"""{m_dir('<p>All 24 clips are made and watched. Making the cut now.</p>', '10:22')}""", state=status("work", "Working · making the cut"), price=price_owner("up to $16.86", "$9.40 spent ·"), dot="work"))

# S7-05 re-making after changes
ban5 = f'<div class="row g2 t-sm" style="padding:10px 12px;background:var(--surface-2);border-radius:8px">{ic("loader-circle","s14 accent-t")}<span>Making Cut 3 with your 2 changes · free · about 40 s. Cut 2 keeps playing until then.</span></div>'
board("S7-05", "Cut editor", "Re-making the cut after changes", wrap(editor_body(changed=(5, 13), banner=ban5, top_right=f'<span class="t-sm muted">Cut 3 in about 40 s</span>'), T1, state=status("work", "Working · making Cut 3"), dot="work"))

# S7-06 making the cut failed
ban6 = f'''<div class="row g2 t-sm" style="padding:10px 12px;background:var(--danger-soft);color:var(--danger);border-radius:8px">{ic("triangle-alert","s14")}<span>Cut 3 couldn’t be made: the music file stops at 0:41, and the cut runs to 0:58. Nothing was charged.</span>
      <span class="grow"></span>{btn("Loop the music to fit · free", "primary")}{btn("Remove the music")}</div>'''
board("S7-06", "Cut editor", "Making the cut failed · one-click fix", wrap(editor_body(changed=(5, 13), banner=ban6, top_right=btn("Download Cut 2", "", "download")), T1, state=status("bad", "Needs a fix"), dot="bad"))

# S7-07 editor (credits)
board("S7-07", "Cut editor", "Editor’s view (credits)", wrap(editor_body(inspector=inspector_broll(editor=True)), T1.replace("Reed", "Kel"), owner=False))
