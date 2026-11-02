import sys, json; sys.path.insert(0,'.')
from bs import call
bd=call("GET","/projects/56/breakdown")["breakdown"]
old={s["id"]:s for sc in bd["scenes"] for s in sc["shots"]}
W,G,K,D,N="char:12","char:1","char:14","char:99","char:101"
def sh(new_id, from_ids, secs, cam, action, chars, line_from=None, scr=None, react=None):
    lines=sorted({n for i in from_ids for n in old[i]["script_lines"]})
    src=old[line_from] if line_from else None
    return dict(id=new_id,script_lines=lines,speaker=src["speaker"] if src else None,line=src["line"] if src else None,
                action=action,reaction=react,camera=cam,seconds=secs,character_ids=chars,place_id=None,moment=None,
                screen_ids=scr if scr is not None else [])
S=[
 # scene 1
 [sh("1.1",["1.1"],2.2,"Medium wide over the couch toward the doorway, slow push in","Wyatt lies on the couch in a sea of pizza boxes, swiping hard on his phone with his tongue poking out in concentration, while Goth GF leans in the doorway behind him, spooning cereal and rolling her eyes.",[W,G],"1.1"),
  sh("1.2",["1.2","1.3","1.4"],1.6,"Low-angle close-up on Wyatt, phone glow on his face","Wyatt doesn't look up, smug and stubborn, a cocky grin into his phone; then the glow on his face flashes pink and his eyes go wide.",[W],"1.2"),
  sh("1.3",["1.5","1.6"],2.2,"Wide, handheld, quick tilt down as he falls","Disbelief, then pure joy that someone matched with him: Wyatt bolts upright, stares at the phone, pumps his fist so hard he tips off the couch, pizza boxes flying, and lands on the floor still grinning at the screen.",[W])],
 # scene 2
 [sh("2.1",["2.1","2.2"],2.6,"Medium two-shot across the candlelit table, slow push in","After a white flash: the date, gorgeous in red, grabs both of Wyatt's hands across the table and laughs far too hard, leaning in, eager and a little too intense.",[D,W],"2.2"),
  sh("2.2",["2.3"],1.4,"Close-up on Wyatt, static","Terrified and thrilled at once that she just proposed: Wyatt's face flushes bright red, his mouth opens with nothing coming out, then a goofy smile breaks through.",[W]),
  sh("2.3",["2.4"],2.2,"Medium shot, tilt up as she rises","The date stands, smoothing her red dress, and gives him a slow wink.",[D,W],"2.4"),
  sh("2.4",["2.5"],1.6,"Floor-level low angle under the table, static","As her black heels walk away, a slimy green tentacle slides out from under her hem across the floor, curls, and snaps back out of sight.",[D,W]),
  sh("2.5",["2.6"],1.6,"Close-up on Wyatt, slow push in","Wyatt watches her go with his chin in his hand, love-struck and clueless, sighing it to himself.",[W],"2.6")],
 [sh("2.6",["2.7","2.8"],1.6,"Whip pan to a medium two-shot","Kimchi, in a long mustard trench coat with an earpiece, drops into the date's empty chair and slaps a DATE PATROL badge on the table, rattling the candles; Wyatt jolts back in his seat.",[K,W]),
  sh("2.7",["2.9"],1.8,"Close-up on Kimchi, push in","Kimchi leans in over the badge, dead serious, eyes flicking toward the restroom.",[K],"2.9"),
  sh("2.8",["2.10"],1.0,"Close-up on Wyatt, static","Wyatt stares at him, his smile sliding off his face.",[W],"2.10"),
  sh("2.9",["2.11"],3.0,"Medium close-up two-shot across the table, slow push in","Kimchi taps his earpiece and slides the badge back into his coat, giving the order low and fast.",[K,W],"2.11"),
  sh("2.10",["2.12","2.13"],1.8,"Close-up on Wyatt, rack focus to the chair","Wyatt blinks and Kimchi is gone; the date slides back into the chair, smiling sweetly, and lays her hand over his; Wyatt forces a shaky smile, a bead of sweat on his temple.",[W,D])],
 # scene 3
 [sh("3.1",["3.1","3.2"],2.0,"Wide, tracking alongside them under a huge full moon","The date leads Wyatt by the hand along the moonlit path to a bench; Wyatt keeps glancing nervously at the dark bushes.",[D,W]),
  sh("3.2",["3.3"],1.5,"Close two-shot on the bench, static","She sits close, sweet and soft in the moonlight.",[D,W],"3.3"),
  sh("3.3",["3.4"],0.8,"Close-up on Wyatt, static","Wyatt nods too fast, swallowing.",[W],"3.4"),
  sh("3.4",["3.5"],1.6,"Extreme close-up on the date, slow push in","She leans in unnaturally close, her smile stretching too wide.",[D],"3.5"),
  sh("3.5",["3.6"],1.4,"Low-angle close-up, fast push in, held","Her jaw splits open into a huge mouth of fangs, her throat glowing green, and she holds it, wide and terrifying.",[D,W]),
  sh("3.6",["3.7"],1.2,"Handheld medium shot, tilt down with his fall","Wyatt stumbles backward off the bench onto the grass, pure terror on his face.",[W],"3.7"),
  sh("3.7",["3.8"],1.6,"Ground-level low angle, fast track backward","A green tentacle whips around Wyatt's ankle and drags him across the grass toward her open mouth while he claws at the dirt, panicking.",[W,D])],
 [sh("3.8",["3.9"],1.2,"Low-angle medium shot, whip pan","Kimchi bursts out of the bushes in his mustard trench coat and fires a chunky trap gun, a blue flash.",[K]),
  sh("3.9",["3.10"],1.8,"Wide, static, camera shake on impact","A glowing blue cube slams down over the monster only; the tentacle is cut clean and goes limp; Wyatt, outside the cube, scrambles away backward on the grass, shaking.",[W,D]),
  sh("3.10",["3.11"],1.6,"Low-angle medium shot on Kimchi, slow push in","Kimchi spins the trap gun and holsters it under his coat, cool as ice.",[K],"3.11"),
  sh("3.11",["3.12"],1.4,"Medium two-shot, static","Kimchi yanks Wyatt to his feet and brushes grass off his shoulders; Wyatt is still trembling, eyes darting back at the glowing cube.",[K,W]),
  sh("3.12",["3.13"],2.4,"Medium close-up two-shot, the phone in the foreground","Kimchi pulls out his phone and holds it out to Wyatt, matter-of-fact.",[K,W],"3.13",["screen:3"]),
  sh("3.13",["3.14","3.15"],1.6,"Close-up on Wyatt, slow push in, the phone glow on his face","Wyatt looks from the trapped monster to the fomo screen in Kimchi's hand, catches his breath, and a shaky, hopeful half-smile appears.",[W,K],None,["screen:3"])],
 # scene 4
 [sh("4.1",["4.1","4.2"],1.4,"Over-the-shoulder close-up on the phone in Wyatt's hand","After a white flash: on the couch, Wyatt taps Copy on a top trader in fomo; the position reads +$420, while Goth GF rolls her eyes behind him.",[W,G],None,["screen:18"]),
  sh("4.2",["4.3","4.4"],1.4,"Medium shot, time-lapse push in","Night after night: the clock past 3 a.m., pizza boxes stacking higher, Wyatt hunched and focused in the phone glow.",[W]),
  sh("4.3",["4.5","4.6"],1.4,"Over-the-shoulder close-up on the phone, Goth GF behind","The balance reads $18,900; behind him Goth GF freezes mid-spoonful, staring at the screen.",[W,G],None,["screen:19"]),
  sh("4.4",["4.7"],1.2,"Close-up on Wyatt's hand holding the phone","The fomo Home (rich) screen; the balance reads $348,920.15.",[W],None,["screen:2"]),
  sh("4.5",["4.8"],2.0,"Low-angle wide, fast orbit","Wyatt leaps onto the couch, arms up, roaring with joy, pizza boxes flying; Goth GF drops her cereal bowl and it smashes.",[W,G])],
 # scene 5
 [sh("5.1",["5.1","5.2"],2.0,"Wide, tracking past the skyline, settling on their table","After a white flash: Wyatt in a sharp suit and gold watch lounges smooth and relaxed at a rooftop sushi bar across from a new date in an emerald dress; Kimchi in his mustard trench coat walks past behind, stops, and turns.",[W,N,K]),
  sh("5.2",["5.3"],1.1,"Close-up on Kimchi, snap zoom","Kimchi pulls his sunglasses down his nose, half amused.",[K],"5.3"),
  sh("5.3",["5.4"],1.3,"Over-Kimchi's-shoulder close-up on the phone","Wyatt grins and turns his phone to Kimchi; the balance reads $348,920.15.",[W,K],None,["screen:2"]),
  sh("5.4",["5.5"],1.3,"Medium two-shot, quick push in","Kimchi slaps Wyatt a proud dap.",[K,W],"5.5"),
  sh("5.5",["5.6"],1.6,"Tight two-shot, Kimchi at Wyatt's ear, slow push in","Kimchi leans down to Wyatt's ear and whispers it, deadpan.",[K,W],"5.6"),
  sh("5.6",["5.7","5.8"],2.0,"Close-up on the new date, slow push in, held","Wyatt's date smiles sweetly, then her pupils snap into gold reptile slits, green scales ripple up her neck, and a long forked tongue flicks out twice.",[N,W]),
  sh("5.7",["5.9"],1.4,"Close-up on Wyatt, static, held","Horror creeping in that it's happening again: the colour drains from Wyatt's face, his chopsticks freeze in midair, the sushi drops.",[W])],
 # scene 6
 [sh("6.1",["6.1","6.2"],1.8,"Medium close-up, Wyatt facing the camera","Still rattled, Wyatt leans toward the camera, glancing back over his shoulder at her.",[W,N],"6.1"),
  sh("6.2",["6.3"],4.0,"Medium close-up, Wyatt facing the camera, slow push in onto the phone","Wyatt holds his phone up to the lens beside a shaky grin; the fomo Home (rich) screen, the balance reads $348,920.15; his eyes flick nervously sideways toward her as he speaks.",[W],"6.3",["screen:2"])],
]
# scenes keep their ids/heading; clip groups
scenes=bd["scenes"]
groups=[S[0],S[1]+S[2],S[3]+S[4],S[5],S[6],S[7]]
for sc,shots in zip(scenes,groups): sc["shots"]=shots
cl=[("c1",S[0],"Wyatt on the floor grinning at the match; white flash into the restaurant."),
    ("c2",S[1],"Wyatt sighs 'She's perfect'; a hand slaps a badge on the table."),
    ("c3",S[2],"Wyatt's forced smile as her hand covers his; cut to the moonlit park."),
    ("c4",S[3],"The tentacle drags Wyatt toward her mouth; Kimchi bursts out of the bushes."),
    ("c5",S[4],"Wyatt's shaky half-smile in the fomo glow; white flash."),
    ("c6",S[5],"Goth GF's bowl smashes; white flash to the rooftop."),
    ("c7",S[6],"Wyatt frozen as the sushi drops; he turns to the camera."),
    ("c8",S[7],"end")]
tmpl=dict(bd["clips"][0]); clips=[]
import math
for cid,shots,seam in cl:
    c=dict(tmpl); c.update(id=cid,shot_ids=[s["id"] for s in shots],seconds=max(4,math.ceil(sum(s["seconds"] for s in shots))),seam=seam); clips.append(c)
bd["clips"]=clips
r=call("PUT","/projects/56/breakdown",bd); print(r.get("problems"))
print([(c["id"],c["seconds"]) for c in clips], "total", sum(c["seconds"] for c in clips))
