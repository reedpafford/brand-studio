"""S3: the video, one director chat with its preview panel. Desktop 1440 + phone 390."""
from lib import *

T = "Beer gut doctor rant"
CRUMB = f'Resilia {ic("chevron-right","s12")} Week of 3 Nov'
MORE = f'<span class="iconbtn">{ic("ellipsis","s14")}</span>'
STOP = btn("Stop", "", "circle-stop") + MORE


def side_info(rows):
    return "".join(f'<div class="row between t-sm"><span class="muted">{k}</span><span class="w5 num">{v}</span></div>' for k, v in rows)


def all_done():
    return {(si, fi): "done" for si, (_, fr) in enumerate(SCENES) for fi in range(len(fr))}


def redo_marks():
    st = all_done(); st[(1, 2)] = "fresh"; st[(2, 3)] = "fresh"; st[(4, 1)] = "fresh"
    return st


def report_card(owner=True, needs=None, cost=None):
    cost = cost or ("$9.84 spent of up to $16.86" if owner else "96 credits used of up to 164 (59% of the budget)")
    needs = needs or '<span class="muted">Nothing. It’s ready to post.</span>'
    return f"""<div class="card"><div class="hd"><span class="w6 t-sm">Delivery note</span><span class="grow"></span>{status('ok','Delivered')}</div>
    <div class="bd col g3">
      <div class="col g1"><span class="t-xs w6 muted">What I made</span><p class="t-sm">A 0:58 rant: Dr. Pickle in the bottom corner over glossy anatomy B-roll, 6 scenes, 24 clips. It opens on the glowing spine with “Your gut after the weekend” before the first second ends.</p></div>
      <div class="col g1"><span class="t-xs w6 muted">What I watched and redid</span>
        <div class="col g1 t-sm">
          <div class="row g2 start"><span class="tag new">0:14</span><span>Clip 7: cartoon eyes landed on the stomach. Remade on Seedance 2.0.</span></div>
          <div class="row g2 start"><span class="tag new">0:31</span><span>Clip 13: Dr. Pickle’s lips slipped behind “bloated”. Re-timed to the words.</span></div>
          <div class="row g2 start"><span class="tag new">0:47</span><span>Clip 20: words burned into the picture. Remade without them.</span></div>
        </div></div>
      <div class="col g1"><span class="t-xs w6 muted">What I’m unsure of</span><p class="t-sm">The capsule holds for 1.5 s at the end. If it feels long, say “shorter end” and I’ll trim it (free).</p></div>
      <div class="col g1"><span class="t-xs w6 muted">What I need from you</span><p class="t-sm">{needs}</p></div>
    </div>
    <div class="ft t-sm"><span class="muted num">{cost}</span><span class="grow"></span><span class="t-sm accent-t w5">Watch the changes</span></div></div>"""


def progress(title, sub, st, open_=False, current=None, waiting=None, tone="now", steps=None, scenes=None):
    icon = {"now": ic("loader-circle", "s14 accent-t"), "wait": ic("clock", "s14 warn-t"), "done": ic("circle-check-big", "s14 ok-t"),
            "bad": ic("triangle-alert", "s14 bad-t"), "stop": ic("circle-stop", "s14 muted")}[tone]
    w = f'<div class="row g2 t-sm" style="padding:8px 10px;margin-top:10px;background:var(--warning-soft);color:var(--warning);border-radius:6px">{ic("clock","s14")}<span>{waiting}</span></div>' if waiting else ""
    s = ""
    if open_:
        s = f'<div class="steps" style="margin-top:10px;border-top:1px solid var(--border);padding-top:4px">{steps}</div>'
    tog = f'<span class="t-sm muted row g1">{"Hide steps" if open_ else "Every step"} {ic("chevron-down","s12")}</span>'
    return f"""<div class="card"><div class="hd">{icon}<span class="t-sm w6">{title}</span><span class="t-sm muted ell">· {sub}</span><span class="grow"></span>{tog}</div>
    <div class="bd">{filmstrip(st, current=current, scenes=scenes)}{w}{s}</div></div>"""


def step(state, text, sub=""):
    i = {"done": ic("check", "s12"), "now": ic("loader-circle", "s12"), "todo": "", "wait": ic("clock", "s12"), "bad": ic("x", "s12")}[state]
    sb = f'<div class="t-xs muted">{sub}</div>' if sub else ""
    return f'<div class="step"><span class="ic {state}">{i}</span><div class="grow"><div class="{"w5" if state == "now" else ""}">{text}</div>{sb}</div></div>'


WORK_STEPS = "".join([
    step("done", "Read the script, the Dr. Pickle guide and Resilia’s brand kit"),
    step("done", "Treatment and plan: 6 scenes, 24 clips, about 60 s"),
    step("done", "Cast: Dr. Pickle and his cloned voice, both saved in Resilia"),
    step("done", "Voice track: 58.2 s, words checked against the script"),
    step("done", "Stills: 24 drawn, 2 redrawn (the capsule label faced away)"),
    step("done", "Clip prompts written · B-roll on Seedance 2.0, host on P-Video", "Seedance 2.0 is the Dr. Pickle default; P-Video lip-syncs the host"),
    step("now", "Making takes: 14 of 24", "Clip 15 · scene 4 · 6 s · about 3 min"),
    step("now", "Watching each take as it lands: 12 watched, 1 redone", "Clip 7: cartoon eyes landed on the stomach. Remaking it ($0.32)."),
    step("todo", "Lay Dr. Pickle over the B-roll, music under him"),
    step("todo", "Watch and listen to the whole cut, then deliver"),
])


def chat_col(title, state, price, thread, comp=None, pin="", banner="", right=STOP, locks=None, crumb=CRUMB, bottom=True, narrow=False):
    comp = comp if comp is not None else composer()
    return f"""<section class="chat{' narrow' if narrow else ''}">{chat_head(title, crumb, state, price, locks=locks, right=right, narrow=narrow)}{banner}
      <div class="thread{' bottom' if bottom else ''}">{thread}</div>{pin}{comp}</section>"""


def clips_panel_live(st):
    """Preview panel while working: the Clips tab filling in, grouped by scene."""
    rows = []
    for si, (nm, frames) in enumerate(SCENES[:4]):
        fr = []
        for fi, f in enumerate(frames):
            s = st.get((si, fi), "done")
            if s == "todo":
                fr.append(empty_media(64, 114))
            elif s == "working":
                fr.append(empty_media(64, 114, "working", f'<span class="play" style="color:var(--accent-text)">{ic("loader-circle","s20")}</span>'))
            else:
                fr.append(media(f, 64, 114, tag=False, cls="redo" if s == "redo" else ""))
        done = sum(1 for fi in range(len(frames)) if st.get((si, fi), "done") in ("done", "redo", "fresh"))
        rows.append(f'<div class="col g2"><div class="row g2 t-sm"><span class="w6">Scene {si+1} · {nm}</span><span class="muted">{done} of {len(frames)}</span></div><div class="row g2">{"".join(fr)}</div></div>')
    return f'<div class="col g4">{"".join(rows)}<span class="t-xs muted">Scenes 5–6 start when these finish. Pictures marked test sample are from the paid tests.</span></div>'


def cut_panel_delivered(owner=True):
    dl = btn("Download MP4", "primary lg", "download")
    return f"""<div class="row g5 start">
        {player('drp_2', 300, 533, '0:14', '0:58', 24)}
        <div class="col g4 grow">
          <div class="col g1"><span class="t-lg">Final cut</span><span class="t-sm muted">0:58 · 9:16 · 24 clips · made 10:25</span></div>
          <div class="col g2">{dl}{btn('Download every clip (.zip)', 'lg')}{btn('Open the cut editor', 'lg', 'scissors')}</div>
          <div class="hr"></div>
          <div class="col g2"><span class="t-xs w6 muted">Changed after watching</span>
            <div class="row g2">{media('pk1', 40, 71, tag=False, cls='fresh')}{media('drp_6', 40, 71, tag=False, cls='fresh')}{media('drp_2', 40, 71, tag=False, cls='fresh')}</div>
            <span class="t-xs muted">Marked until you’ve watched them.</span></div>
          <div class="hr"></div>
          {side_info([('Style', 'Dr. Pickle'), ('Presenter', 'Dr. Pickle · cloned voice'), ('B-roll', 'Seedance 2.0 · 480p · silent'), ('Spent' if owner else 'Credits used', '$9.84' if owner else '96 credits')])}
        </div></div>
      <div class="col g2"><div class="row between"><span class="t-xs w6 muted">The video, scene by scene</span><span class="t-xs muted">Click a frame to jump there</span></div>
      {filmstrip(redo_marks(), 24, 43)}</div>"""


ME = ("Reed", "R", "")
KEL = ("Kel", "K", "ed")
FIRST = m_me("Make the Dr. Pickle rant from the beer gut script. Keep it under a minute, end on the capsule.", "10:02", *ME[:2], ME[2])


# S3-01 new idea, before the first move
def s01():
    script = '<div class="script" style="font-size:13px;line-height:1.55;margin-top:6px;padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:6px">DR. PICKLE: Your gut after the weekend? A brewery with a pulse.<br>DR. PICKLE: Every pint sits there and ferments…<br><span class="muted">+ 11 more lines</span></div>'
    thread = f"""{m_me('Make the Dr. Pickle rant from this script. Keep it under a minute, end on the capsule.' + script, '10:02', *ME)}
      {m_dir('<div class="row g2 t-sm muted"><span class="typing"><i></i><i></i><i></i></span>Reading the script, the Dr. Pickle guide and Resilia’s brand kit</div>', '10:02')}"""
    body = f"""<div class="col center g3" style="flex:1;text-align:center">
        <div class="row g2">{empty_media(64,114)}{empty_media(64,114)}{empty_media(64,114)}</div>
        <span class="t-lg">The plan shows here first</span>
        <span class="t-sm muted" style="max-width:340px">The director writes a treatment, then the scenes fill in with stills and clips as they’re made. The cut plays here when it’s ready.</span></div>"""
    return rail() + chat_col(T, status("work", "Working · starting"), price_owner("estimating…", "Nothing spent"), thread, composer("Add anything the director should know")) + panel("Plan", body)


# S3-02 treatment posted, start-of-run OK (the owner's)
def s02():
    okcard = ask_card("Ready to start", "Make it for up to $16.86?",
                      "That’s the most this run can charge: the first takes and their checks, up to 2 remakes a clip, and my own time. Usually it’s nearer $10.",
                      ways=(), foot=btn("Make it · up to $16.86", "primary lg") + btn("Change the plan first", "lg") + '<span class="grow"></span><span class="t-xs muted">Nothing is spent until you press.</span>')
    thread = f"""{FIRST}
      {m_dir('<p>Here’s how I’ll make it. Tell me if anything should change before I spend.</p>' + treatment_card(compact=True), '10:03')}
      {m_dir(okcard, '10:03')}"""
    shots = [("Hook", ["Glowing spine, slow push in", "Dr. Pickle turns to camera", "Heart close-up, pulsing"]),
             ("What beer does", ["Beer down the see-through throat", "Skeleton slumps on the couch", "The stomach swells", "Dr. Pickle points"]),
             ("The bloat", ["Gut lining, inflamed", "Bloat glows green", "Dr. Pickle, arms crossed", "Close on the gut"]),
             ("Worse at night", ["Tossing in bed, belly glowing", "The clock: 3:12 AM", "Skeleton sits up", "Dr. Pickle shrugs"]),
             ("The fix", ["The Resilia capsule", "The gut calms, blue", "Coffee swapped for water"]), ("Ending", ["Dr. Pickle: “Link in my bio.”", "Capsule hold"])]
    cards = "".join(f'<div class="list" style="padding:8px 12px"><div class="row g2"><span class="w6 t-sm">{i+1}. {b}</span><span class="grow"></span><span class="t-xs muted">{len(sh)} clips</span></div><div class="col" style="margin-top:4px">{"".join(f'<span class="t-xs muted" style="line-height:18px">{j+1}. {x}</span>' for j, x in enumerate(sh))}</div></div>' for i, (b, sh) in enumerate(shots))
    body = f'<div class="row between"><span class="t-lg">Plan</span><span class="t-sm muted">6 scenes · 24 clips · about 60 s</span></div><div class="col g2">{cards}</div>'
    return rail(tree=resilia_tree(T, {T: "need"})) + chat_col(T, status("need", "Waiting for your OK"), price_owner("up to $16.86", "Nothing spent"), thread, right=MORE) + panel("Plan", body)


st_work = progress_states(3, working={(3, 2), (3, 3)}, todo_from=2, redo=[(1, 2)])


# S3-03 working, progress card collapsed
def s03():
    thread = f"""{FIRST}
      {sysline('check', 'You approved up to $16.86 · 10:04')}
      {m_dir('<p>Started. Dr. Pickle is saved in Resilia, so I used him and his cloned voice without asking.</p>', '10:04')}
      {m_dir(progress('Making the clips', '14 of 24 · scene 4 of 6', st_work, current=3), '10:16', '<span class="t-xs muted">· updating</span>')}"""
    body = clips_panel_live(st_work)
    return rail() + chat_col(T, status("work", "Working"), price_owner("up to $16.86", "$6.12 spent"), thread) + panel("Clips", body)


# S3-04 working, progress card open
def s04():
    thread = f"""{sysline('check', 'You approved up to $16.86 · 10:04')}
      {m_dir(progress('Making the clips', '14 of 24 · scene 4 of 6', st_work, open_=True, current=3, steps=WORK_STEPS), '10:16', '<span class="t-xs muted">· updating</span>')}"""
    body = clips_panel_live(st_work)
    return rail() + chat_col(T, status("work", "Working"), price_owner("up to $16.86", "$6.12 spent"), thread) + panel("Clips", body)


# S3-05 asking: one question, everything else carries on (UGC video, presenter avatar)
def s05():
    card = ask_card("The director needs you · 1 of 1", "Who should be the presenter?",
                    "He talks to camera for the whole video, so every take uses this face. Resilia has two saved people who fit.",
                    saved=[("still_ugc_still", "Mark", "Saved · used in 6 videos"), ("skit_1", "Dana", "Saved · used in 2")],
                    gen=("Generate options", "3 faces · up to $0.24 · not saved"),
                    foot=btn("Use Mark", "primary") + '<span class="grow"></span><span class="t-xs muted">I’m writing the B-roll prompts meanwhile.</span>', sel=0)
    st = progress_states(0, todo_from=0, scenes=UGC_SCENES)
    pr = progress("Waiting on 1 answer", "everything else carries on", st, tone="wait", scenes=UGC_SCENES,
                  waiting="The presenter. Meanwhile: B-roll stills 3 of 4 drawn, prompts being written.")
    thread = f"""{m_me('UGC testimonial: a guy who used to be bloated after pizza nights. Talk to camera, kitchen, phone-real.', '11:20', *ME)}
      {m_dir('<p>Treatment is in the Plan tab. One thing I can’t decide on my own:</p>', '11:21')}
      {m_dir(card, '11:21')}
      {m_dir(pr, '11:22', '<span class="t-xs muted">· updating</span>')}"""
    pin = f'<div class="pinbar">{ic("circle-question-mark","s14")}1 question waiting · The presenter<span class="grow"></span><span class="w6">Show</span></div>'
    locks = default_locks(fmt="Presenter", sty="UGC", castn="needs you", cast=False, length="about 30 s")
    body = f"""<div class="row between"><span class="t-lg">Cast</span><span class="t-sm muted">1 role</span></div>
      <div class="list" style="padding:14px;display:flex;gap:14px;align-items:center">{empty_media(72,128,'empty', '<span class="play" style="color:var(--warning)">'+ic('circle-question-mark','s20')+'</span>')}
        <div class="col g1"><span class="w6">Presenter</span><span class="t-sm muted">Talks to camera the whole time</span>{status('need','Waiting on your answer in the chat')}</div></div>
      <div class="row between" style="margin-top:8px"><span class="t-sm w6">B-roll stills, made meanwhile</span><span class="t-xs muted">3 of 4 · the 2 talking clips wait for the presenter</span></div>
      <div class="row g2 wrap">{media('ugcb_4',64,114,tag=False)}{media('ug1',64,114,tag=False)}{media('ug2',64,114,tag=False)}{empty_media(64,114,'working')}</div>"""
    return rail(tree=resilia_tree("Bloated after pizza")) + chat_col("Bloated after pizza", status("need", "Needs you"), price_owner("up to $7.40", "$0.42 spent"), thread, pin=pin, locks=locks) + panel("Cast", body, [("Cut", None), ("Clips", "6"), ("Cast", "1"), ("Plan", None), ("Script", None)])


# S3-06/07 waiting for the owner's OK on budget
def budget_card(owner=True):
    if owner:
        return ask_card("Past the budget · needs your OK", "Redo clips 9 and 12? That goes $1.54 past the budget.",
                        "Both have Dr. Pickle’s lips out of time with “ferments” and “pint”. Redoing them takes this video to up to $18.40 ($16.30 spent plus up to $2.10); its budget is $16.86.",
                        ways=(), foot=btn("Approve · up to $2.10 more", "primary") + btn("Keep the cut as it is") + '<span class="grow"></span><span class="t-xs muted">Everything else is done.</span>',
                        body_extra=f'<div class="row g2">{media("drp_3",54,96,tag=False,cls="redo")}{media("drp_4",54,96,tag=False,cls="redo")}<span class="t-xs muted" style="align-self:flex-end">Clip 9 · Clip 12</span></div>')
    return ask_card("Waiting for the owner’s OK", "Redo clips 9 and 12? That goes 15 credits past the budget.",
                    "Both have Dr. Pickle’s lips out of time. The owner has been asked; nothing is charged while it waits.",
                    ways=(), state="held", foot=btn("Withdraw the request") + '<span class="grow"></span><span class="t-xs muted">Sent 10:31 · you’ll see the answer here</span>',
                    body_extra=f'<div class="row g2">{media("drp_3",54,96,tag=False,cls="redo")}{media("drp_4",54,96,tag=False,cls="redo")}<span class="t-xs muted" style="align-self:flex-end">Clip 9 · Clip 12</span></div>')


def s06(owner=True):
    st = all_done(); st[(2, 0)] = "redo"; st[(3, 0)] = "redo"
    who = KEL  # Kel's video; the owner sees the same chat
    pr = progress("Waiting for the owner’s OK" if not owner else "Waiting for your OK", "2 redos past the budget", st, tone="wait")
    thread = f"""{m_me('Make the IPA one from the published script, Dr. Pickle style.', '10:05', *who)}
      {m_dir('<p>All 24 clips are made and I’ve watched them. Two need redoing and that’s more than the budget has left.</p>', '10:31')}
      {m_dir(budget_card(owner), '10:31')}
      {m_dir(pr, '10:31')}"""
    price = price_owner("budget $16.86", "$16.30 spent ·") if owner else price_editor("97% of the budget", "159 credits ·")
    state = status("wait", "Waiting for your OK" if owner else "Waiting for the owner")
    body = f"""<div class="row g5 start">{player('drp_3', 300, 533, '0:22', '0:58', 38, '')}
      <div class="col g3 grow"><span class="t-lg">Cut 1 · ready to watch</span><span class="t-sm muted">Made before the redos. It’s usable as is; clips 9 and 12 have the lips slightly late.</span>
      {btn('Download this cut', 'lg', 'download')}<div class="hr"></div>
      {side_info([('Budget', '$16.86' if owner else '164 credits'), ('Spent', '$16.30' if owner else '159 credits'), ('The redos', 'up to $2.10' if owner else 'up to 20 credits')])}</div></div>"""
    return rail(tree=resilia_tree("Why IPAs hit harder"), role="owner" if owner else "editor") + chat_col("Why IPAs hit harder", state, price, thread, right=MORE) + panel("Cut", body)


# S3-08 stopped by a person
def s08():
    st = progress_states(2, todo_from=1)
    thread = f"""{FIRST}
      {sysline('check', 'You approved up to $16.86 · 10:04')}
      {m_dir(progress('Stopped', '11 of 24 clips made', st, tone='stop'), '10:14')}
      {sysline('circle-stop', 'Reed stopped the director at 10:14. Nothing more is being spent.')}
      {m_dir('<p>Stopped. The 11 finished clips are kept. Tell me what to change, or carry on where I left off.</p><div class="row g2" style="margin-top:4px">' + btn('Carry on · up to $10.74 more', 'primary') + btn('Start the plan again') + '</div>', '10:14')}"""
    return rail(tree=resilia_tree(T, {T: "stop"})) + chat_col(T, status("stop", "Stopped"), price_owner("up to $16.86", "$6.12 spent ·"), thread, right=MORE) + panel("Clips", clips_panel_live(st))


# S3-09/10 delivered
def s09(owner=True):
    who = ME if owner else KEL
    thread = f"""
      {m_me("Make the Dr. Pickle rant from the beer gut script. Keep it under a minute, end on the capsule.", "10:02", *who)}
      {sysline('check', 'Started · up to $16.86 approved by Reed' if owner else 'Started · up to 164 credits, inside the video’s budget')}
      {m_dir(progress('Made in 22 min', '24 clips · 3 redone after watching', redo_marks(), tone='done'), '10:25')}
      {m_dir('<p>Here’s the cut. I watched and listened to every take and the whole cut twice.</p>' + report_card(owner), '10:25')}"""
    price = price_owner("$16.86", "$9.84 of up to") if owner else price_editor("164 credits", "96 of up to")
    return rail(tree=resilia_tree(T, {T: "ok"}), role="owner" if owner else "editor") + chat_col(T, status("ok", "Delivered"), price, thread, composer("Say what to change: “shorter end”, “swap the B-roll at 0:14”…"), right=MORE) + panel("Cut", cut_panel_delivered(owner))


# S3-11 a step failed, with a one-click fix (today's real error, rewritten)
def s11():
    st = progress_states(1, todo_from=0, scenes=SKEL_SCENES)
    fail = f"""<div class="card" style="border-color:#f1c6c1"><div class="hd" style="background:var(--danger-soft);color:var(--danger);border-radius:8px 8px 0 0">{ic('triangle-alert','s14')}<span class="t-sm w6">Clip 4 couldn’t be made</span></div>
      <div class="bd col g3" style="padding-top:10px"><p class="t-sm">Clip 4 runs 115 s, but Seedance 1 Lite makes at most 12 s a clip. Nothing was charged.</p>
      <p class="t-sm">I can split it into 10 clips at the sentence breaks. The words don’t change, and the split itself is free.</p>
      <div class="row g2">{btn('Split it into 10 clips · free', 'primary')}{btn('Use a model that makes longer clips…')}</div></div></div>"""
    thread = f"""{m_me('Narrated night-time bloat ad from the Resilia script, Skeleton style.', '09:40', *ME)}
      {sysline('check', 'You approved up to $12.10 · 09:41')}
      {m_dir(progress('Stopped at clip 4', '3 of 18 clips made', st, tone='bad', scenes=SKEL_SCENES), '09:52')}
      {m_dir(fail, '09:52')}"""
    return rail(tree=resilia_tree("Night-time bloat")) + chat_col("Night-time bloat", status("bad", "Needs a fix"), price_owner("up to $12.10", "$1.20 spent ·"), thread, right=MORE,
                                       locks=default_locks(fmt="Narrated", sty="Skeleton", castn="Bare-bones", length="about 45 s")) + panel("Plan", f'<div class="list">' + "".join(f'<div class="lrow"><span class="w6" style="width:70px">Clip {i}</span><span class="grow muted ell">{t}</span><span class="num">{d}</span>{s}</div>' for i, t, d, s in [(1, "Skeleton sits up in bed, belly glowing", "4 s", status("ok", "Made")), (2, "Close on the glowing gut", "3 s", status("ok", "Made")), (3, "The clock: 3:12 AM", "3 s", status("ok", "Made")), (4, "The narrator explains why it’s worse at night…", "115 s", status("bad", "Too long for the model")), (5, "Skeleton reaches for water", "4 s", status("stop", "Waiting"))]) + '</div><span class="t-sm muted">Clip 4 holds the whole middle of the script. Splitting it at the sentence breaks gives 10 clips of 8–12 s.</span>', [("Cut", None), ("Clips", "18"), ("Cast", "1"), ("Plan", None), ("Script", None)])


# S3-12 revising after a note
def s12():
    st = redo_marks(); st[(1, 2)] = "working"; st[(5, 1)] = "redo"
    thread = f"""{m_dir('<p>Here’s the cut. I watched and listened to every take and the whole cut twice.</p><div class="card" style="padding:8px 12px"><span class="t-sm muted">Delivery note · Cut 1 · 0:58 · $9.84</span></div>', '10:25')}
      {m_me('Swap the B-roll at 0:14 for something less gross, and make the ending shorter.', '10:40', *ME)}
      {m_dir('<p>On it. Two changes:</p><div class="col g1 t-sm"><div class="row g2 start"><span class="tag n">0:14</span><span>Clip 7: a cleaner see-through stomach, no eyes. New B-roll, up to $0.32.</span></div><div class="row g2 start"><span class="tag n">0:56</span><span>Ending: hold the capsule 0.6 s instead of 1.5 s. A trim, free.</span></div></div><p class="t-sm muted">Nothing else goes out of date. Cut 2 follows in about 4 min.</p>', '10:40')}
      {m_dir(progress('Revising', '1 of 2 changes', st, tone='now', current=1), '10:41', '<span class="t-xs muted">· updating</span>')}"""
    body = f"""<div class="row g5 start">{player('drp_2', 300, 533, '0:14', '0:58', 24)}
      <div class="col g3 grow"><div class="seg"><span class="on">Cut 1</span><span>Cut 2 · making</span></div><span class="t-sm muted">Cut 1 stays watchable until Cut 2 is ready.</span>
      <div class="hr"></div><span class="t-xs w6 muted">Going out of date</span>
      <div class="row g2">{media('pk1',48,85,tag=False,cls='stale')}{media('drp_1',48,85,tag=False,cls='stale')}</div>
      <span class="t-xs muted">Clip 7 and the ending</span></div></div>
      <div class="col g2"><span class="t-xs w6 muted">The video, scene by scene</span>{filmstrip(st, 24, 43)}</div>"""
    return rail() + chat_col(T, status("work", "Working · revising"), price_owner("up to $17.18", "$9.84 spent ·"), thread) + panel("Cut", body)


# S3-13 a long Movie (100+ clips): progress counts by scene
def s13():
    scenes = [("1. The eviction notice", 9, 9), ("2. Laughed out of the bank", 11, 11), ("3. Night shift", 8, 8), ("4. The mentor’s diner", 12, 12),
              ("5. First trade", 10, 7), ("6. Time skip", 6, 0), ("7. Back at the bank", 11, 0), ("8. The landlord", 12, 0)]
    frames = ["skit_1", "skit_2", "skit_3", "ugc_4", "skit_2"]
    rows = "".join(f'<div class="row g3 t-sm" style="padding:6px 0;border-top:1px solid var(--border)"><span class="grow ell {"w5" if 0 < d < n else ""}">{nm}</span><div class="prog" style="width:120px"><i style="width:{int(100*d/n)}%"></i></div><span class="num muted" style="width:44px;text-align:right">{d}/{n}</span></div>' for nm, n, d in scenes)
    pr = f"""<div class="card"><div class="hd">{ic('loader-circle','s14 accent-t')}<span class="t-sm w6">Making the clips</span><span class="t-sm muted">· 47 of 118 · scene 5 of 13</span><span class="grow"></span><span class="t-sm muted row g1">Every step {ic('chevron-down','s12')}</span></div>
      <div class="bd"><div class="prog" style="margin-bottom:8px"><i style="width:40%"></i></div>{rows}<div class="t-xs muted" style="padding-top:6px">+ 5 more scenes · about 2 h 10 min left</div></div></div>"""
    thread = f"""{m_me('Make the 7-minute drama from the landlord script. Movie style.', '08:10', *ME)}
      {sysline('check', 'You approved up to $96.40 · 08:14')}
      {m_dir(pr, '09:46', '<span class="t-xs muted">· updating</span>')}"""
    groups = "".join(f'<div class="col g2"><div class="row g2 t-sm"><span class="w6">{nm}</span><span class="muted">{d} of {n}</span><span class="grow"></span>{ic("chevron-down","s12 muted")}</div><div class="row g1">{"".join(media(frames[(i+j)%5], 34, 60, tag=False) if j < d else empty_media(34,60) for j in range(min(n, 14)))}</div></div>' for i, (nm, n, d) in enumerate(scenes[2:6]))
    body = f'<div class="row between"><span class="t-lg">Clips</span><div class="seg"><span class="on">All 118</span><span>Needs you 1</span><span>Flagged 3</span><span>Redone 4</span></div></div><span class="t-xs muted">Scenes 1–2 folded · 20 clips done</span>{groups}'
    tree = [(0, "folderopen", "Movies", {"cnt": "2"}), (1, "idea", "The landlord (7 min)", {"dot": "work", "on": True}), (1, "idea", "Laughed out of the bank", {"dot": "ok"}),
            (0, "folder", "House remakes", {"cnt": "21"}), (0, "folder", "Week of 3 Nov", {"cnt": "8"}), (0, "unsorted", "Unsorted", {"cnt": "4"})]
    return rail("fomo", tree=tree) + chat_col("The landlord (7 min)", status("work", "Working"), price_owner("up to $96.40", "$41.20 spent ·"), thread,
                                               locks=default_locks(fmt="Dialogue", sty="Movie", castn="Marcus, Dana +4", length="about 7 min"), crumb=f'fomo {ic("chevron-right","s12")} Movies') + panel("Clips", body, [("Cut", None), ("Clips", "118"), ("Cast", "6"), ("Plan", None), ("Script", None)])


# S3-14 an editor asks to change a locked line
def s14():
    reply = f"""<p>The script’s words are set for this script, so I can’t change “beer gut”. Here’s what I can change instead:</p>
      <div class="col g2" style="margin-top:2px">
        <div class="way" style="flex:none">{ic('mic','s14')}<div><span class="w6">Say it softer</span><small>Dr. Pickle says it with less sneer. Redo the voice line and clip 2 · up to 4 credits</small></div></div>
        <div class="way" style="flex:none">{ic('film','s14')}<div><span class="w6">Cut away while it’s said</span><small>Show the B-roll instead of Dr. Pickle’s face on that line · free</small></div></div>
        <div class="way" style="flex:none">{ic('clock','s14')}<div><span class="w6">Shorter pause after it</span><small>Tighten 0.4 s · free</small></div></div></div>"""
    thread = f"""{m_dir('<p>Here’s the cut.</p><div class="card" style="padding:8px 12px"><span class="t-sm muted">Delivery note · Cut 1 · 0:58 · 96 credits</span></div>', '10:25')}
      {m_me('Can we change “beer gut” to “belly”? It feels a bit harsh.', '10:44', *KEL)}
      {m_dir(reply, '10:44')}"""
    return rail(tree=resilia_tree(T, {T: "ok"}), role="editor") + chat_col(T, status("ok", "Delivered"), price_editor("164 credits", "96 of up to"), thread, right=MORE) + panel("Script", f'<div class="list" style="padding:16px"><div class="row g2" style="margin-bottom:10px">{ic("lock","s14 muted")}<span class="t-sm muted">Published script · the words are set</span></div><div class="script" style="font-size:13px">DR. PICKLE: Your <span style="background:var(--mark);padding:0 2px">beer gut</span> after the weekend? A brewery with a pulse.<br>DR. PICKLE: Every pint sits there and ferments.<br>DR. PICKLE: That’s not a belly. That’s a science project.<br>DR. PICKLE: And at 3 AM? It throws a party.<br><span class="muted">+ 9 more lines</span></div></div>')


# S3-15 loading
def s15():
    sk = lambda w, h=12: f'<div class="skel" style="width:{w}px;height:{h}px"></div>'
    thread = "".join(f'<div class="msg"><div class="skel" style="width:24px;height:24px;border-radius:50%"></div><div class="col g2">{sk(120)}{sk(380)}{sk(300)}</div></div>' for _ in range(3))
    head = f'<div class="chathead"><div class="row g2">{sk(160)}</div><div class="row g3">{sk(240,18)}</div><div class="row g2">{sk(110,26)}{sk(90,26)}{sk(80,26)}</div></div>'
    chat = f'<section class="chat">{head}<div class="thread">{thread}</div>{composer()}</section>'
    body = f'<div class="row g5 start"><div class="skel" style="width:300px;height:533px;border-radius:10px"></div><div class="col g3">{sk(160,18)}{sk(200)}{sk(220,36)}{sk(220,36)}</div></div>'
    return rail() + chat + panel("Cut", body)


# S3-16 the connection drops; the director keeps working on the server
def s16():
    banner = f'<div class="banner n">{ic("wifi-off","s14")}<span>You’re offline. The director keeps working on the server; this page catches up when you’re back.</span><span class="grow"></span><span class="w5">Retry</span></div>'
    thread = f"""{sysline('check', 'You approved up to $16.86 · 10:04')}
      {m_dir(progress('Making the clips', 'last update 10:16', st_work, current=3), '10:16')}"""
    return rail() + chat_col(T, status("work", "Working"), price_owner("up to $16.86", "$6.12 spent ·"), thread, banner=banner, comp=composer("You can type; it sends when you’re back")) + panel("Clips", clips_panel_live(st_work))


if __name__ == "__main__":
  board("S3-01", "Video: chat + preview", "New idea, before the first move", s01())
  board("S3-02", "Video: chat + preview", "Treatment posted · start-of-run OK (owner)", s02())
  board("S3-03", "Video: chat + preview", "Working · progress card folded", s03())
  board("S3-04", "Video: chat + preview", "Working · progress card open", s04())
  board("S3-05", "Video: chat + preview", "Asking · one question, the rest carries on", s05())
  board("S3-06", "Video: chat + preview", "Waiting for the owner’s OK · owner", s06(True))
  board("S3-07", "Video: chat + preview", "Waiting for the owner’s OK · editor", s06(False))
  board("S3-08", "Video: chat + preview", "Stopped by a person", s08())
  board("S3-09", "Video: chat + preview", "Delivered · owner", s09(True))
  board("S3-10", "Video: chat + preview", "Delivered · editor", s09(False))
  board("S3-11", "Video: chat + preview", "A step failed · one-click fix", s11())
  board("S3-12", "Video: chat + preview", "Revising after a note", s12())
  board("S3-13", "Video: chat + preview", "Long Movie · 118 clips · when Movie is on", s13())
  board("S3-14", "Video: chat + preview", "Editor asks to change a locked line", s14())
  board("S3-15", "Video: chat + preview", "Loading", s15())
  board("S3-16", "Video: chat + preview", "Offline · the director keeps working", s16())
