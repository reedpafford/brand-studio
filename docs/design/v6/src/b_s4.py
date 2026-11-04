"""S4: ask cards. Every kind and every state, at their real chat width (560 px), plus one in context."""
from lib import *
from b_s3 import chat_col, progress, progress_states, ME, KEL, MORE, panel as _p

W = 560


def cell(caption, card, note=""):
    n = f'<span class="t-xs muted">{note}</span>' if note else ""
    return f'<div class="col g2" style="width:{W}px"><div class="row g2"><span class="t-sm w6">{caption}</span>{n}</div>{card}</div>'


def sheet(title, sub, cells):
    cols = [cells[0::2], cells[1::2]]
    c = "".join(f'<div class="col g8">{"".join(x)}</div>' for x in cols)
    return f'<div class="col g2" style="margin-bottom:28px"><span class="t-2xl">{title}</span><span class="t-sm muted">{sub}</span></div><div class="row g8 start">{c}</div>'


def voice_row(name, sub, sel=False, saved=True):
    bars = "".join(f'<i style="display:inline-block;width:2px;height:{h}px;background:{"var(--accent)" if sel else "#b9bcc6"};border-radius:1px"></i>' for h in [6, 10, 14, 8, 16, 12, 6, 10, 18, 12, 8, 14, 10, 6, 12, 16, 10, 8, 12, 6, 9, 13, 7, 11])
    return f'''<div class="row g3" style="padding:8px 10px;border:1px solid {"var(--accent)" if sel else "var(--border)"};border-radius:6px;{"background:var(--accent-soft)" if sel else ""}">
      <span class="iconbtn b" style="width:28px;height:28px">{ic("play","s12")}</span><div class="col"><span class="t-sm w6">{name}</span><span class="t-xs muted">{sub}</span></div>
      <span class="grow"></span><span class="row" style="gap:2px;align-items:center">{bars}</span></div>'''


# ---------- kinds ----------
k_character = ask_card("The director needs you", "Who plays the husband?",
    "He’s in 9 of 14 clips, so every take uses this face. Resilia has these saved.",
    saved=[("still_ugc_still", "Mark", "Saved · 6 videos"), ("skit_2", "Tom", "Saved · 1 video")],
    gen=("Generate options", "3 looks · up to $0.24 · this video only"), foot=btn("Use Mark", "primary") + btn("Skip: you decide") + '<span class="grow"></span><span class="t-xs muted">Waiting on this only</span>', sel=0)

k_presenter = ask_card("The director needs you", "Which avatar presents this one?",
    "UGC talks to camera from one still photo, so this is the face for the whole video.",
    saved=[("still_ugc_still", "Mark · kitchen", "Saved · UGC"), ("skit_3", "Dana · hallway", "Saved · UGC")],
    gen=("Generate options", "3 avatars on Nano Banana Pro · up to $0.36"), foot=btn("Use Mark · kitchen", "primary") + '<span class="grow"></span><span class="t-xs muted">Voice comes next, if needed</span>', sel=0)

k_voice = ask_card("The director needs you", "Which voice should Mark have?",
    "He talks for the whole 30 s. Phone-real and relaxed fits UGC.",
    ways=(), body_extra='<div class="col g2"><span class="sec">Saved in Resilia</span>' + voice_row("Roger", "Relaxed, mid · saved · used in 3 videos", True) + voice_row("Dr. Pickle (cloned)", "Deep, fixed · his own voice") + '</div>'
    + '<div class="col g2"><span class="sec">Other ways</span><div class="ways"><div class="way dashed">' + ic("upload", "s14") + '<div><span class="w6">Upload a sample</span><small>Clone it once · up to $3.00</small></div></div><div class="way">' + ic("message-square", "s14") + '<div><span class="w6">Describe it</span><small>“Late 40s, tired, warm”</small></div></div></div></div>',
    foot=btn("Use Roger", "primary") + '<span class="grow"></span><span class="t-xs muted">Samples play here; nothing is spent</span>')

k_place = ask_card("The director needs you", "Where’s Mark’s kitchen?",
    "Every talking shot is there. A saved place keeps it the same in all 9 clips.",
    saved=[("ugc_5", "Mark’s kitchen", "Saved · 4 videos"), ("ug1", "Coffee counter", "Saved")],
    gen=("Generate options", "3 kitchens · up to $0.24 · this video only"), foot=btn("Use Mark’s kitchen", "primary") + '<span class="grow"></span>', sel=0)

k_product = ask_card("The director needs you", "Is this the capsule to show at the end?",
    "The ending holds on the product for 1.5 s, so its label must read right.",
    saved=[("ug2", "Resilia capsule", "Saved · product"), ("ugc_4", "Glass + capsule", "Saved · still")],
    ways=("upload", "reply"), foot=btn("Use the capsule", "primary") + '<span class="grow"></span><span class="t-xs muted">No pack photo saved yet</span>', sel=0)

k_brand_item = ask_card("The director needs you", "Which fomo screen shows the win?",
    "Scene 5 needs the app on his phone with a winning trade. These are fomo’s real screens; I’ll change the coin and numbers to fit.",
    saved=[("fomo_token-up", "Token up", "fomo screen"), ("fomo_home-rich", "Home, rich", "fomo screen"), ("fomo_home", "Home", "fomo screen")],
    saved_label="fomo’s app screens", ways=("upload", "reply"), foot=btn("Use Token up", "primary") + '<span class="grow"></span><span class="t-xs muted">The logo and UI stay as they are</span>', sel=0)

story_opts = f'''<div class="row g2">
  <div class="col g2" style="flex:1;padding:10px;border:1px solid var(--accent);border-radius:8px;background:var(--accent-soft)"><div class="row g2"><span class="tag new">A · my pick</span></div>
    <span class="t-sm w6">He bins the pint, opens the capsule</span><span class="t-xs muted">Clear before and after; the product is the turn. Fits the guide’s “product at the key moment”.</span></div>
  <div class="col g2" style="flex:1;padding:10px;border:1px solid var(--border);border-radius:8px"><div class="row g2"><span class="tag n">B</span></div>
    <span class="t-sm w6">He keeps the pint and toasts the camera</span><span class="t-xs muted">Funnier and more on his side, but the capsule is only on screen for 1 s.</span></div></div>'''
k_story = ask_card("The director needs you", "How should it end?", "The script ends on “link in my bio” but doesn’t say what we see. Both work; it changes the last 2 clips.",
    ways=("reply",), body_extra=story_opts, foot=btn("Go with A", "primary") + btn("Go with B") + '<span class="grow"></span><span class="t-xs muted">I’ll go with A at 11:00 if I don’t hear back</span>')

k_question = ask_card("The director needs you", "Who’s this for?", "It changes the hook. Men 30–50 who drink at weekends get the brewery joke; “anyone bloated” gets a softer open.",
    ways=("reply",), foot='<span class="t-xs muted">Answer in a word or two. I’m drawing the stills meanwhile.</span>')

k_start = ask_card("Ready to start", "Make it for up to $16.86?", "That’s the most this run can charge: the first takes and their checks, up to 2 remakes a clip, and my own time. Usually it’s nearer $10.",
    ways=(), foot=btn("Make it · up to $16.86", "primary") + btn("Change the plan first") + '<span class="grow"></span><span class="t-xs muted">Nothing spent yet</span>')

k_budget_o = ask_card("Past the budget · needs your OK", "Redo clips 9 and 12? That goes $1.54 past the budget.",
    "Dr. Pickle’s lips are late on “ferments” and “pint”. $16.30 spent plus up to $2.10 makes up to $18.40; the budget is $16.86.", ways=(),
    foot=btn("Approve · up to $2.10 more", "primary") + btn("Keep the cut as it is"))

k_budget_e = ask_card("Waiting for the owner’s OK", "Redo clips 9 and 12? That goes 15 credits past the budget.",
    "The owner has been asked. Nothing is charged while it waits.", ways=(), state="held",
    foot=btn("Withdraw the request") + '<span class="grow"></span><span class="t-xs muted">Sent 10:31</span>')

board("S4-01", "Ask cards", "Kinds 1 of 2: cast, presenter, voice, place, product, brand item",
      sheet("Ask cards: what the director can ask", "Saved items come first. Upload and Reply are always there. Generate shows its price before anything runs, and what it makes stays with this video.",
            [cell("Character or cast role", k_character, "saved first"), cell("Presenter avatar", k_presenter, "UGC still image"),
             cell("Voice", k_voice, "samples play free"), cell("Place", k_place),
             cell("Product shot", k_product, "no Generate: must be the real product"), cell("Missing brand item", k_brand_item, "fomo’s real screens")]), "s", h=1740)

board("S4-02", "Ask cards", "Kinds 2 of 2: story choice, open question, start OK, budget",
      sheet("Ask cards: choices and money", "Story choices show the director’s pick and why. Money cards say what the most is, never less.",
            [cell("Story choice (A or B)", k_story), cell("Open question (reply in words)", k_question),
             cell("Start-of-run OK (owner, or an editor’s send held)", k_start), cell("Past the budget · owner", k_budget_o),
             cell("Past the budget · editor", k_budget_e, "never “ask Reed”")]), "s", h=1220)

# ---------- states ----------
uploading = ask_card("The director needs you", "Who plays the husband?", None, ways=(),
    body_extra=f'<div class="row g3" style="padding:10px;border:1px dashed var(--border-strong);border-radius:8px">{media("skit_2",48,64,tag=False)}<div class="col g1 grow"><span class="t-sm w6">husband-ref.jpg</span><div class="prog"><i style="width:62%"></i></div><span class="t-xs muted">Uploading · 1.4 of 2.2 MB</span></div><span class="iconbtn">{ic("x","s14")}</span></div>')

generating = ask_card("The director needs you", "Who plays the husband?", None, ways=(),
    options=[(None, "Option 1", "drawing…"), (None, "Option 2", "drawing…"), (None, "Option 3", "drawing…")],
    foot=f'<span class="row g2 t-sm muted">{ic("loader-circle","s14")}Drawing 3 looks · up to $0.24 · about 40 s</span><span class="grow"></span>{btn("Cancel")}')

ready = ask_card("The director needs you", "Who plays the husband?", None, ways=(),
    options=[("skit_2", "Option 1", "Late 30s, tired"), ("ugcb_4", "Option 2", "Mid 40s, stubble"), ("still_ugc_still", "Option 3", "50, warm")], sel=("g", 1),
    foot=btn("Use option 2", "primary") + btn("More like 2", "", "refresh-cw", "$0.24") + btn("Change something…") + '<span class="grow"></span><span class="t-xs muted">$0.18 spent</span>')

answered = f'''<div class="ask done"><div class="ahd">{ic("check","s14")}<span>Answered</span><span class="grow"></span><span>Change</span></div>
  <div class="abd" style="flex-direction:row;align-items:center;gap:12px">{media("still_ugc_still",40,54,tag=False)}<div class="col"><span class="t-sm w6">Husband: Mark</span><span class="t-xs muted">Saved in Resilia · picked by Reed, 11:24</span></div></div></div>'''

answered_owner = f'''<div class="ask done"><div class="ahd">{ic("check","s14")}<span>Answered by the owner</span></div>
  <div class="abd" style="flex-direction:row;align-items:center;gap:12px">{media("skit_3",40,54,tag=False)}<div class="col"><span class="t-sm w6">Presenter: Dana · hallway</span><span class="t-xs muted">Reed answered this for you at 11:31. The video carried on.</span></div></div></div>'''

not_needed = f'''<div class="ask done"><div class="ahd">{ic("x","s14")}<span>No longer needed</span></div>
  <div class="abd"><span class="t-sm">Which kitchen? <span class="muted">You locked the cast to Mark, who comes with his kitchen, so I used that.</span></span></div></div>'''

failed = ask_card("The director needs you", "Who plays the husband?", None, ways=(),
    body_extra=f'<div class="row g2 t-sm" style="padding:10px;background:var(--danger-soft);color:var(--danger);border-radius:6px">{ic("triangle-alert","s14")}<span>The picture service was busy and made nothing. Nothing was charged.</span></div>',
    foot=btn("Try again · up to $0.24", "primary") + btn("Upload instead", "", "upload"))

held = ask_card("Waiting for the owner’s OK", "Who plays the husband?", None, ways=(), state="held",
    body_extra='<span class="t-sm">You asked for 3 generated looks (up to 3 credits). You’re past this week’s allowance, so the owner has been asked. Nothing is charged while it waits.</span>',
    foot=btn("Withdraw") + btn("Upload instead", "", "upload") + '<span class="grow"></span><span class="t-xs muted">Sent 11:26</span>')

queue = f'''<div class="col g2"><div class="pinbar" style="margin:0">{ic("circle-question-mark","s14")}2 questions waiting · The husband · How it ends<span class="grow"></span><span class="w6">Next</span></div>
  <div class="composer" style="margin:0"><div class="ph">Tell the director what to change</div><div class="bar"><span class="iconbtn">{ic("upload","s14")}</span><span class="grow"></span><span class="send off">{ic("arrow-up","s14")}</span></div></div>
  <span class="t-xs muted">Pinned above the message box. Tap to jump to the next open card. The idea shows a “needs you” dot in the tree.</span></div>'''

board("S4-03", "Ask cards", "States: uploading, generating, ready, answered, not needed, failed, held, several",
      sheet("Ask cards: states", "One card moves through these states in place. Answered cards fold to one line and can be changed.",
            [cell("Uploading", uploading, "used for this video; add people to the brand in Cast & places"), cell("Generating options", generating, "price and time shown"),
             cell("Options ready", ready, "pick, more like it, or change"), cell("Answered (folded)", answered),
             cell("Answered by the owner, on an editor’s card", answered_owner), cell("No longer needed", not_needed),
             cell("Generating failed", failed, "free retry when nothing was charged"), cell("Editor’s paid generation held for the owner", held),
             cell("Several questions waiting", queue)]), "s", h=1520)


# S4-04 in context: options ready, at 1440
def s4_04():
    from b_s3 import T, CRUMB
    tree = [(0, "folderopen", "UGC testimonials", {"cnt": "9"}), (1, "idea", "Caught with the pizza boxes", {"dot": "need", "on": True}), (1, "idea", "Date-night bloat", {"dot": "ok"}),
            (1, "idea", "Gym guy gut", {"dot": "ok"}), (0, "folder", "Week of 3 Nov", {"cnt": "6"}), (0, "folder", "Dr. Pickle rants", {"cnt": "14"}), (0, "unsorted", "Unsorted", {"cnt": "2"})]
    st = progress_states(0, todo_from=0, scenes=SKIT_SCENES)
    thread = f"""{m_me('A wife and husband skit: she catches him hiding pizza boxes. Realistic, Movie look.', '11:20', *ME)}
      {m_dir('<p>Resilia has no saved woman who fits, so I made two (up to $0.24). Mark plays the husband (saved).</p>', '11:23')}
      {m_dir(ask_card("The director needs you", "Who plays the wife?", None, ways=(), options=[("skit_3", "Option 1", "Late 30s, glasses"), ("skit_1", "Option 2", "Mid 30s, cardigan")], sel=("g", 0),
             foot=btn("Use option 1", "primary") + btn("More like 1", "", "refresh-cw", "$0.24") + btn("Change something…") + '<span class="grow"></span><span class="t-xs muted">$0.24 spent</span>'), '11:23')}
      {m_dir(progress('Waiting on 1 answer', 'everything else carries on', st, tone='wait', scenes=SKIT_SCENES, waiting='The wife. Meanwhile: the kitchen stills and Mark’s lines are being made.'), '11:23')}"""
    body = f"""<div class="row between"><span class="t-lg">Cast</span><span class="t-sm muted">2 roles</span></div>
      <div class="list">
        <div class="lrow" style="padding:12px">{media('still_ugc_still',60,80,tag=False)}<div class="col g1 grow"><span class="w6">Husband · Mark</span><span class="t-sm muted">Saved in Resilia · locked</span></div>{status('ok','Approved')}</div>
        <div class="lrow" style="padding:12px">{media('skit_3',60,80,tag=False)}<div class="col g1 grow"><span class="w6">Wife · option 1?</span><span class="t-sm muted">Made for this video · not saved</span></div>{status('need','Waiting on you')}</div></div>
      <span class="t-sm w6" style="margin-top:6px">Option 1, larger</span>{media('skit_3', 220, 391)}"""
    return rail(tree=tree) + chat_col("Caught with the pizza boxes", status("need", "Needs you"), price_owner("up to $24.10", "$0.24 spent ·"), thread,
                                       pin=f'<div class="pinbar">{ic("circle-question-mark","s14")}1 question waiting · The wife<span class="grow"></span><span class="w6">Show</span></div>',
                                       locks=default_locks(fmt="Dialogue", sty="Movie", castn="Mark + 1", cast=False, length="about 40 s"), crumb=f'Resilia {ic("chevron-right","s12")} UGC testimonials') + _p("Cast", body, [("Cut", None), ("Clips", "14"), ("Cast", "2"), ("Plan", None), ("Script", None)])


board("S4-04", "Ask cards", "In context: generated options ready · when Movie is on", s4_04())
