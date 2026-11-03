"""Phone (390) boards: the main state of each screen, plus states whose phone layout differs."""
from lib import *
from b_s3 import redo_marks, all_done, progress_states, report_card, step, ME, KEL
from b_s4 import k_presenter, k_budget_e, voice_row
from b_s01 import IDEAS


def pscreen(top, body, bottom="", tabs=None):
    return f'{phone_status()}{top}<div class="pbody">{body}</div>{bottom}{tabs if tabs is not None else ""}<div class="home-ind"><i></i></div>'


def ptop(left, title, right="", sub=None):
    s = f'<span class="t-xs muted">{sub}</span>' if sub else ""
    return f'<div class="ptopbar">{left}<div class="col grow" style="min-width:0"><span class="w6 ell">{title}</span>{s}</div>{right}</div>'


BACK = f'<span class="iconbtn">{ic("chevron-left","s20")}</span>'
MOREP = f'<span class="iconbtn">{ic("ellipsis","s20")}</span>'


def scene_row(st, w=44, h=78):
    """Phone: one frame per scene (the first finished one), with the scene's count under it."""
    out = []
    for si, (nm, frames) in enumerate(SCENES):
        done = [f for fi, f in enumerate(frames) if st.get((si, fi)) in ("done", "fresh", "redo")]
        changed = any(st.get((si, fi)) in ("fresh", "redo") for fi in range(len(frames)))
        pic = media(done[0], w, h, tag=False, cls="fresh" if changed else "") if done else empty_media(w, h, "working" if any(st.get((si, fi)) == "working" for fi in range(len(frames))) else "empty")
        out.append(f'<div class="col g1" style="align-items:center">{pic}<span class="t-xs muted num">{len(done)}/{len(frames)}</span></div>')
    return f'<div class="row" style="gap:8px;flex-wrap:nowrap">{"".join(out)}</div>'


def pprogress(title, sub, st, tone="now", waiting=None):
    icon = {"now": ic("loader-circle", "s14 accent-t"), "wait": ic("clock", "s14 warn-t"), "done": ic("circle-check-big", "s14 ok-t")}[tone]
    w = f'<div class="row g2 t-sm" style="padding:8px 10px;margin-top:10px;background:var(--warning-soft);color:var(--warning);border-radius:6px">{ic("clock","s14")}<span>{waiting}</span></div>' if waiting else ""
    return f'''<div class="card"><div class="hd">{icon}<span class="t-sm w6">{title}</span><span class="grow"></span>{ic("chevron-down","s14 muted")}</div>
      <div class="bd"><span class="t-xs muted">{sub}</span><div style="margin-top:8px">{scene_row(st)}</div>{w}</div></div>'''


def vtop(title="Beer gut doctor rant", st=None, on="Chat", price="up to $16.86"):
    st = st or status("work", "Working")
    seg = f'<div class="row" style="padding:8px 12px;background:var(--surface);border-bottom:1px solid var(--border);gap:8px"><div class="seg" style="flex:1"><span class="{"on" if on == "Chat" else ""}" style="flex:1;justify-content:center">Chat</span><span class="{"on" if on == "Preview" else ""}" style="flex:1;justify-content:center">Preview</span></div></div>'
    return ptop(BACK, title, MOREP, None).replace('</div><span class="iconbtn">', f'<div class="row g2">{st}<span class="t-xs muted num">· {price}</span></div></div><span class="iconbtn">', 1) + seg


pcomp = '<div class="composer"><div class="ph">Tell the director what to change</div><div class="bar"><span class="iconbtn">' + ic("upload", "s14") + '</span><span class="grow"></span><span class="send off">' + ic("arrow-up", "s14") + '</span></div></div>'

st_work = progress_states(3, working={(3, 2), (3, 3)}, todo_from=2, redo=[(1, 2)])

# P-01 tree
tree_rows = "".join(f'<div class="row g3" style="height:48px;padding:0 16px;border-bottom:1px solid var(--border);{"padding-left:40px;" if l else ""}">{ic(i,"s16 muted")}<span class="grow {"w5" if not l else ""}">{n}</span>{f"<span class=t-sm muted>{c}</span>" if c else ""}{d}</div>'
                    for l, i, n, c, d in [(0, "folder-open", "Week of 3 Nov", "10", ""), (1, "film", "Beer gut doctor rant", "", '<span class="dot work"></span>'), (1, "film", "Bloated after pizza", "", '<span class="dot need"></span>'),
                                          (1, "film", "Why IPAs hit harder", "", '<span class="dot wait"></span>'), (0, "folder", "Dr. Pickle rants", "124", ""), (0, "folder", "UGC testimonials", "9", ""), (0, "folder", "Black Friday", "3", ""), (0, "inbox", "Unsorted", "2", "")])
board("P-01", "Phone · folder tree", "Brand and its folders", pscreen(ptop(f'<div class="brandsw" style="padding:0">{BRANDS["Resilia"]}<span>Resilia</span>{ic("chevron-down","s14")}</div>', "", f'<span class="iconbtn">{ic("search","s20")}</span><span class="iconbtn">{ic("folder-plus","s20")}</span>').replace('<div class="col grow" style="min-width:0"><span class="w6 ell"></span></div>', '<span class="grow"></span>'),
      f'<div style="background:var(--surface)">{tree_rows}</div><div style="padding:16px">{btn("New video","primary lg","plus")}</div>', tabs=phone_tabs()), "p")

# P-02 folder
cards = "".join(f'<div class="icard">{media(f, 175, 230)}<div class="col g1"><span class="t" style="font-size:14px">{t}</span>{status(k, s.split(" · ")[0])}<span class="m">{sty} · {p}</span></div></div>' for t, f, k, s, sty, ln, who, when, p, c in IDEAS[:4])
board("P-02", "Phone · brand home", "An open folder", pscreen(ptop(BACK, "Week of 3 Nov", f'<span class="iconbtn">{ic("search","s20")}</span>', "Resilia · 10 ideas · 2 need you"),
      f'<div class="row g2" style="padding:10px 14px"><div class="seg"><span class="on">All</span><span>Needs you 2</span><span>Done 5</span></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px 12px;padding:4px 14px">{cards}</div>', tabs=phone_tabs()), "p")

# P-03 new video
fmts = "".join(f'<div class="stylecard{" sel" if n == "Presenter" else ""}" style="width:120px;flex:none">{media(i,120,70,style="border-radius:0")}<div class="info"><span class="t-sm w6">{n}</span></div></div>' for n, i in [("Dialogue", "skit_2"), ("Narrated", "sk1"), ("Presenter", "drp_2"), ("Song", "px2")])
stys = "".join(f'<div class="stylecard{" sel" if n == "Dr. Pickle" else ""}" style="width:100px;flex:none">{media(i,100,130,style="border-radius:0",extra=f"<span class=play><i>{ic(chr(112)+chr(108)+chr(97)+chr(121),chr(115)+chr(49)+chr(52))}</i></span>")}<div class="info"><span class="t-sm w6">{n}</span><span class="t-xs muted">{b}</span></div></div>' for n, i, b in [("Dr. Pickle", "drp_1", "Glossy anatomy B-roll"), ("Skeleton", "sk2", "Inside the body"), ("UGC", "ugc_1", "Phone-real"), ("House", "house_marcus_rain", "Near-real inserts")])
board("P-03", "Phone · new video", "Filled in · price shown", pscreen(ptop(f'<span class="iconbtn">{ic("x","s20")}</span>', "New video", "", "Resilia · Week of 3 Nov"),
      f'''<div class="col g4" style="padding:14px">
        <div class="seg" style="align-self:flex-start"><span class="on">Paste</span><span>Saved script</span><span>Use a reel</span></div>
        <div style="border:1px solid var(--border-strong);border-radius:12px;background:var(--surface);padding:12px"><div class="script" style="font-size:13px">DR. PICKLE: Your gut after the weekend? A brewery with a pulse.<br>DR. PICKLE: Every pint sits there and ferments.<br><span class="muted">+ 11 more lines</span></div></div>
        <div class="col g2"><span class="t-sm w6">Format</span><div class="row g2" style="overflow:hidden">{fmts}</div></div>
        <div class="col g2"><span class="t-sm w6">Style</span><div class="row g2" style="overflow:hidden">{stys}</div></div>
        <div class="row g2 wrap">{chip("Dr. Pickle","Cast","users")}{chip("9:16","Shape")}{chip("Week of 3 Nov","Folder","folder")}</div></div>''',
      bottom=f'<div style="padding:10px 14px;border-top:1px solid var(--border);background:var(--surface)" class="col g1">{btn("Make it · up to $16.86","primary lg").replace("btn primary lg","btn primary lg").replace("<span class","<span style=width:100%;justify-content:center class",1)}<span class="t-xs muted" style="text-align:center">The most it can charge, redos included</span></div>'), "p")

# P-04 chat working
board("P-04", "Phone · video", "Chat · working", pscreen(vtop(), f'''<div class="thread bottom" style="flex:1">{m_me("Make the Dr. Pickle rant from the beer gut script. Under a minute.", "10:02", *ME)}
      {sysline("check", "You approved up to $16.86")}{m_dir(pprogress("Making the clips", "14 of 24 · scene 4 of 6 · 1 redone after watching", st_work), "10:16")}</div>''', bottom=pcomp), "p")

# P-05 preview: the cut
board("P-05", "Phone · video", "Preview · the delivered cut", pscreen(vtop(st=status("ok", "Delivered"), on="Preview", price="$9.84 of up to $16.86"),
      f'''<div class="col g3" style="padding:14px;align-items:center">{player("drp_2", 240, 426, "0:14", "0:58", 24)}
        <div class="row g2" style="width:100%">{btn("Download MP4","primary lg","download").replace('class="btn','style="flex:1;justify-content:center" class="btn')}{btn("Edit","lg","scissors")}</div>
        <div style="width:100%">{scene_row(redo_marks(), 44, 78)}</div><span class="t-xs muted" style="align-self:flex-start">3 clips changed after watching are outlined</span></div>'''), "p")

# P-06 asking
board("P-06", "Phone · video", "Asking · the card in the chat, pinned bar", pscreen(vtop("Bloated after pizza", status("need", "Needs you"), price="up to $7.40"),
      f'<div class="thread bottom" style="flex:1">{m_dir(k_presenter, "11:21")}</div>',
      bottom=f'<div class="pinbar" style="margin:0 12px 6px">{ic("circle-question-mark","s14")}1 question waiting<span class="grow"></span><span class="w6">Show</span></div>{pcomp}'), "p")

# P-07 waiting for the owner (editor)
board("P-07", "Phone · video", "Waiting for the owner’s OK · editor", pscreen(vtop("Why IPAs hit harder", status("wait", "Waiting for the owner")).replace("up to $16.86", "159 credits"),
      f'<div class="thread bottom" style="flex:1">{m_dir("<p>All 24 clips are made. Two need redoing, past the budget.</p>", "10:31")}{m_dir(k_budget_e, "10:31")}</div>', bottom=pcomp), "p")

# P-08 delivered report
board("P-08", "Phone · video", "Chat · delivered with the note", pscreen(vtop(st=status("ok", "Delivered"), price="$9.84 of up to $16.86"),
      f'<div class="thread bottom" style="flex:1">{m_dir("<p>Here’s the cut. I watched and listened to every take and the whole cut twice.</p>" + report_card(True), "10:25")}</div>', bottom=pcomp), "p")

# P-09 cast
roles = "".join(f'<div class="role" style="padding:10px">{media(i,60,80,tag=False) if i else empty_media(60,80)}<div class="col g1 grow"><span class="w6">{n}</span><span class="t-xs muted">{s}</span>{st}{a}</div></div>' for i, n, s, st, a in [
    ("house_marcus_rain", "Marcus", "Look for this video", status("ok", "Approved"), ""), ("sheet_gothgf", "Jade", "Saved in fomo", status("ok", "Locked"), ""),
    (None, "Chase", "Clips 2–4 wait for him", status("need", "Needs a look"), f'<div class="row g2" style="margin-top:6px">{btn("Pick saved","primary","users")}{btn("Upload","","upload")}</div>')])
board("P-09", "Phone · video", "Preview · Cast", pscreen(vtop("Three dimes to a penthouse", status("need", "Needs you"), on="Preview").replace("up to $16.86", "up to $19.40"),
      f'<div class="col g2" style="padding:12px 14px"><div class="seg"><span>Cut</span><span>Clips</span><span class="on">Cast</span><span>Plan</span><span>Script</span></div><div class="col g2" style="margin-top:6px">{roles}</div></div>'), "p")

# P-10 clips list (long)
scn = "".join(f'<div class="row g2" style="padding:12px 14px;border-bottom:1px solid var(--border);background:var(--surface)">{ic("chevron-right","s14 muted")}<span class="w6 grow">{n}</span><span class="t-sm muted num">{d}</span></div>' for n, d in [("1. The eviction notice", "9/9"), ("2. Laughed out of the bank", "11/11"), ("3. Night shift", "8/8"), ("4. The mentor’s diner", "12/12")])
open5 = "".join(f'<div class="row g3" style="padding:8px 14px;border-bottom:1px solid var(--border);background:var(--surface)">{media(i,32,57,tag=False) if i else empty_media(32,57)}<div class="col grow"><span class="t-sm w6">Clip {n}</span><span class="t-xs muted">{t}</span></div>{s}</div>' for n, i, t, s in [
    (41, "skit_1", "Marcus opens the app", status("ok", "Done")), (42, "skit_2", "Close on the chart", status("ok", "Done")), (44, "skit_3", "Dana leans in", status("need", "Flagged")), (48, None, "He hits Buy", status("work", "Making"))])
board("P-10", "Phone · video", "Preview · Clips, 118 grouped by scene", pscreen(vtop("The landlord (7 min)", status("work", "Working"), on="Preview").replace("up to $16.86", "up to $96.40"),
      f'<div class="col" style="padding:10px 0 0"><div class="row g2" style="padding:0 14px 10px"><div class="seg"><span class="on">All 118</span><span>Flagged 3</span><span>Redone 4</span></div></div>{scn}<div class="row g2" style="padding:12px 14px;border-bottom:1px solid var(--border);background:var(--surface-2)">{ic("chevron-down","s14 muted")}<span class="w6 grow">5. First trade</span><span class="t-sm muted">7/10</span></div>{open5}</div>'), "p")

# P-11 one clip
board("P-11", "Phone · video", "One clip open", pscreen(ptop(BACK, "Clip 7", "", "Scene 2 · 4 s · Seedance 2.0"),
      f'''<div class="col g3" style="padding:14px"><div class="row g2 start t-sm" style="padding:10px;background:var(--accent-soft);color:var(--accent-text);border-radius:8px">{ic("eye","s14")}<span><b class="w6">Found:</b> cartoon eyes on the stomach. <b class="w6">Did:</b> remade it. $0.32.</span></div>
        <div class="row g3">{media("pk1pv",170,302,play=True)}{media("pk1",170,302,play=True,cls="sel")}</div><div class="row g3 t-xs muted"><span style="width:170px">Take 1 · dropped</span><span>Take 2 · in the cut</span></div>
        <div class="col g2">{btn("Change this…","lg","pencil","$0.32")}{btn("Another take","lg","refresh-cw","$0.32")}{btn("Add sound effects","lg","volume-2","$0.01")}</div></div>'''), "p")

# P-12 cut on a phone
edits = "".join(f'<div class="row g3" style="padding:10px 14px;border-bottom:1px solid var(--border);background:var(--surface)"><span class="tag new">{t}</span><span class="t-sm grow">{e}</span><span class="t-sm accent-t">Undo</span></div>' for t, e in [("0:14", "Clip 7 swapped (the director)"), ("0:24", "Clip 9 re-timed to the words"), ("0:26", "Dr. Pickle moved left"), ("0:56", "Ending trimmed 0.9 s")])
board("P-12", "Phone · cut", "The cut on a phone: play, edits, ask", pscreen(ptop(BACK, "Cut 2", "", "0:58 · Beer gut doctor rant"),
      f'<div class="col" style="padding:12px 0 0"><div class="row" style="justify-content:center;padding-bottom:12px">{player("drp_2",200,356,"0:14","0:58",24)}</div><span class="t-sm w6" style="padding:4px 14px 8px">Edits in this cut</span>{edits}<span class="t-xs muted" style="padding:10px 14px">The full timeline is on desktop. Ask the director for any edit here.</span></div>',
      bottom=pcomp.replace("Tell the director what to change", "Ask for an edit: “shorter end”")), "p")

# P-13 library
chars = "".join(f'<div class="col g1">{media(i,175,230)}<span class="w6 t-sm">{n}</span><span class="t-xs muted">{s}</span></div>' for i, n, s in [("still_ugc_still", "Mark", "6 videos"), ("still_hostA", "Dr. Pickle", "31 videos"), ("skit_3", "Dana", "2 videos"), ("skit_2", "Tom", "1 video")])
board("P-13", "Phone · library", "Characters", pscreen(ptop(f'<div class="brandsw" style="padding:0">{BRANDS["Resilia"]}<span>Library</span></div>', "", f'<span class="iconbtn">{ic("plus","s20")}</span>').replace('<div class="col grow" style="min-width:0"><span class="w6 ell"></span></div>', '<span class="grow"></span>'),
      f'<div class="row" style="padding:8px 14px;overflow:hidden"><div class="seg" style="white-space:nowrap"><span class="on">Characters</span><span>Places</span><span>Products</span><span>Presenters</span><span>Brand kit</span></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:14px 12px;padding:6px 14px">{chars}</div>', tabs=phone_tabs("Library")), "p")

# P-14 needs you
items = "".join(f'<div class="list" style="padding:12px;display:flex;gap:12px">{media(i,44,78,tag=False)}<div class="col g2 grow"><span class="t-xs muted">{v}</span><span class="t-sm w6">{q}</span><div class="row g2 wrap">{a}</div></div></div>' for i, v, q, a in [
    ("ugc_1", "Bloated after pizza · Resilia", "Who should be the presenter?", btn("Use Mark", "", "check") + btn("Open")), ("drp_3", "Why IPAs hit harder · Resilia", "Redo 2 clips · $1.54 past the budget", btn("Approve · up to $2.10", "primary", "check") + btn("Decline")),
    ("sk2", "Gut check, Kel’s send · Resilia", "Start it · up to $16.40", btn("Approve · up to $16.40", "", "check") + btn("Decline")), ("pk3", "Night-time bloat · Resilia", "Clip 4 couldn’t be made", btn("Split it · free", "", "check"))])
board("P-14", "Phone · needs you", "Owner’s inbox", pscreen(ptop("", "Needs you", "", "4 waiting · every brand"), f'<div class="col g3" style="padding:14px">{items}</div>', tabs=phone_tabs("Needs you")), "p")

# P-15 ask card: options ready (phone)
ready_p = ask_card("The director needs you", "Which avatar presents this one?", None, ways=(),
    options=[("still_ugc_still", "Option 1", "Late 40s, warm"), ("ugcb_4", "Option 2", "Mid 40s, stubble"), ("skit_2", "Option 3", "Late 30s, tired")], sel=("g", 0),
    foot=btn("Use option 1", "primary") + btn("More like 1", "", "refresh-cw", "$0.36") + btn("Change…") + '<span class="grow"></span><span class="t-xs muted">$0.36 spent</span>')
board("P-15", "Phone · video", "Ask card · options ready", pscreen(vtop("Bloated after pizza", status("need", "Needs you"), price="up to $7.40"), f'<div class="thread bottom" style="flex:1">{m_dir(ready_p, "11:24")}</div>', bottom=pcomp), "p")
