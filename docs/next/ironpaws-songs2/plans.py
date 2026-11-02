"""Reed's three round-2 Iron Paws song ads: one scene plan per song, keyed to the first sung line of each scene.
Every line of the song gets a picture; symptoms are exaggerated, causes are made visible, payoffs are warm."""
OWNER = ("Mid-30s woman, the dog's owner, working from home; slim, warm olive skin, wavy chestnut hair in a loose messy bun, "
         "an oversized cream knit sweater over a plain white tee, light-wash jeans, small gold hoop earrings. Kind and worn out at first, relieved and happy by the end.")
DOGS = {
 "song1": ("pit bull", "About 3-year-old male American pit bull terrier, the family dog; muscular stocky build, short glossy blue-grey coat with a white chest blaze, broad head, natural uncropped rose ears, big soulful amber eyes, a plain brown leather collar. Expressive and gentle."),
 "song2": ("Frenchie", "About 4-year-old male French bulldog, the family dog; smooth fawn coat, compact stocky body, big upright bat ears, short flat muzzle with a dark mask, huge round glossy brown eyes, a wrinkled worried brow, a red bandana tied at his neck. Very expressive."),
 "song3": ("golden retriever", "About 5-year-old male golden retriever, the family dog; fluffy golden coat, broad friendly head, soft floppy ears, big warm brown eyes, a goofy open-mouthed grin, a royal blue collar. Playful showman."),
}
X = "STUDIO — DEEP BLUE BACKDROP"
SCENES = {
 "song1": [
  (1,  "INT. KITCHEN — MORNING", ["His owner leans in to greet {the dog}; he yawns and a green cartoon stink cloud with a little fish skeleton puffs out; she recoils, fanning her nose.", "Extreme close-up: {the dog}'s teeth crusted with yellow tartar."]),
  (3,  "INT. BATHROOM — EVENING", ["A slow-motion toothbrush battle: his owner chases {the dog} around the bathroom with a toothbrush, toothpaste flying, {the dog} dodging and wriggling.", "{The dog} sits and gives the camera big innocent eyes.", "His owner slumps against the bathtub, exhausted."]),
  (6,  "INT. LIVING ROOM — DAY", ["His owner offers {the dog} a dental chew; he sniffs it and drops it on the rug.", "At night she wrestles him gently with the toothbrush again.", "She squeezes drops of water additive into his water bowl."]),
  (10, "INT. KITCHEN — DAY", ["His owner sniffs {the dog}'s breath and gives a hopeful thumbs up.", "Wall calendar pages flip by quickly.", "The green stink cloud rolls back in and she slumps over the counter."]),
  (13, "INT. KITCHEN TABLE — NIGHT", ["His owner sits with her head in her hands among a pile of failed dental chews, toothbrushes and bottles.", "{The dog} rests his head on her knee, looking up at her.", "She stares at the products, lost."]),
  (18, X, ["A translucent x-ray view of {the dog}: a glowing line runs from his mouth down to a glowing red gut."]),
  (20, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["The gut's balance tips: round good-bacteria buddies scatter and grumpy purple bad-bacteria blobs multiply.", "The bad-bacteria blobs march up a long pink tunnel toward the mouth.", "In the mouth they paint the teeth yellow and puff green stink clouds.", "A toothbrush scrubs from outside, but the blobs keep marching up from below."]),
  (25, "INT. LIVING ROOM — DAY", ["His owner on the phone, nodding seriously, a notepad in hand.", "She watches videos on her laptop late at night, sticky notes everywhere.", "A lightbulb moment: she sits up straight, eyes wide."]),
  (30, "INT. KITCHEN COUNTER — DAY", ["★ Peanut butter bag — hero shot of the bag on the counter, golden five-star shapes sparkling around it."]),
  (31, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["Tiny probiotic hero buddies rebuild the gut wall brick by brick.", "Bright green parsley leaves swirl up and zap the green stink cloud away.", "A chicory root plants itself and steadies the gut lining."]),
  (34, "INT. KITCHEN — NIGHT", ["★ Peanut butter bag — his owner scoops the green powder from the bag into {the dog}'s food bowl.", "{The dog} leaps mid-air and empties the bowl before it touches the floor; she freezes, holding the empty bowl."]),
  (38, "INT. BEDROOM — MORNING, WEEKS LATER", ["His owner leans close to {the dog}, scrunching her face and bracing for the smell.", "She sniffs: nothing. Her eyes go wide with surprise.", "She lifts his lip: clean, sparkling white teeth."]),
  (41, "INT. LIVING ROOM — WARM LIGHT", ["His owner scratches {the dog}'s ear, sorry, and pulls him into a hug."]),
  (43, X, ["The x-ray {the dog} again: his gut glows a calm healthy gold and his teeth sparkle."]),
  (45, "INT. LIVING ROOM — GOLDEN HOUR", ["★ Peanut butter bag — {the dog} nudges the bag toward the camera with his nose and flashes a big clean smile; his owner smiles behind him."]),
 ],
 "song2": [
  (1,  "EXT. BACKYARD — DAY", ["{The dog} grazes on the lawn like a tiny cow, munching grass, while a real cow over the fence stares at him."]),
  (2,  "INT. LIVING ROOM — DAY", ["His owner sniffs {the dog}'s paw and recoils as a cartoon fish leaps out of the smell."]),
  (3,  "INT. LIVING ROOM — DAY", ["{The dog} scratches himself so frantically he spins in circles on the rug."]),
  (4,  "INT. LIVING ROOM — DAY", ["{The dog} sits and looks earnestly into the camera, his belly flickering with a faint red glow."]),
  (6,  "INT. HOME — DAYS", ["His owner swaps one dog food bag for another.", "A bathtub shampoo bubble storm, {the dog} buried in foam.", "At the front door she wipes his paws with a towel, again and again."]),
  (9,  "INT. LIVING ROOM — DAY", ["{The dog} lies calm for a moment, his owner smiling with relief.", "Then quick beats: he munches grass, sniffs his smelly paw, scratches hard."]),
  (12, "INT. LIVING ROOM — EVENING", ["His owner wipes {the dog}'s paws on the couch while an x-ray glow shows his belly still glowing red inside."]),
  (14, X, ["A translucent x-ray view of {the dog}: his gut glows red and the little good-bacteria lights inside it dim one by one."]),
  (17, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["A giant seesaw inside the gut tips over as the good bacteria leave.", "Grass blades, a fishy smell cloud and itchy red sparks spill out from the tipped seesaw.", "A shampoo bottle and a new food bag bounce off from outside without changing anything."]),
  (22, "INT. LIVING ROOM — DAY", ["His owner on the phone, taking notes.", "She watches videos on her laptop, sticky notes everywhere.", "A lightbulb moment: she sits up, eyes wide."]),
  (27, "INT. KITCHEN COUNTER — DAY", ["★ Peanut butter bag — hero shot of the bag on the counter, golden five-star shapes sparkling around it."]),
  (28, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["Tiny probiotic hero buddies march back into the gut.", "A bright green chlorella wave washes out the grey gunk.", "A chicory root plants itself and the seesaw levels out, balanced."]),
  (31, "INT. KITCHEN — NIGHT", ["★ Peanut butter bag — his owner scoops the green powder from the bag into {the dog}'s bowl.", "{The dog} leaps mid-air and empties the bowl before it touches the floor."]),
  (35, "EXT. BACKYARD — MORNING, WEEKS LATER", ["His owner looks out at the lawn: untouched; {the dog} lies calmly in the sun.", "She sniffs his paw and gives a thumbs up.", "He rests peacefully, not scratching."]),
  (38, "INT. LIVING ROOM — WARM LIGHT", ["His owner scratches {the dog}'s ear, sorry, and hugs him."]),
  (40, X, ["The x-ray {the dog} again: his gut glows a calm healthy gold."]),
  (42, "INT. LIVING ROOM — GOLDEN HOUR", ["★ Peanut butter bag — {the dog} nudges the bag toward the camera with his nose; his owner smiles behind him."]),
 ],
 "song3": [
  (1,  "INT. GAME SHOW SET — BRIGHT", ["{The dog} stands at a game show podium like a host, a giant one-to-ten meter glowing behind him.", "He holds up a paddle and grins at the camera.", "He points a paw at himself with a knowing look."]),
  (5,  "EXT. PARK PATH — DAY", ["On a walk {the dog} grazes on grass, then holds up a scorecard with a big number 4."]),
  (9,  "INT. BEDROOM — MORNING", ["{The dog} wakes up squinting through crusty eyes and holds up a scorecard with a big number 6.", "An x-ray flicker shows toxins pushing out through his eyes."]),
  (13, "INT. LIVING ROOM — DAY", ["{The dog} licks his paws in a frenzy, then holds up a scorecard with a big number 8.", "A red inflammation glow rises from inside his body to his skin."]),
  (17, "INT. KITCHEN — DAY", ["His owner leans in and his breath wilts a houseplant on the counter.", "{The dog} holds up a scorecard with a big number 9 as the meter behind him flashes red."]),
  (21, "INT. LIVING ROOM — DAY", ["His owner sits on the couch looking sheepish.", "{The dog} puts his head on her lap to comfort her.", "She shrugs, sad and confused."]),
  (25, "INT. GAME SHOW SET — BRIGHT", ["{The dog} leans toward the camera as if sharing a secret.", "Behind him four glowing symptom icons merge into one glowing gut."]),
  (28, X, ["A translucent x-ray view of {the dog}: dry kibble, a tap water glass and artificial treats float into his dull, worn gut.", "Then a healthy golden glow spreads outward from his gut through his whole body."]),
  (31, "INT. KITCHEN COUNTER — DAY", ["★ Peanut butter bag — his owner finds the bag on the counter, golden five-star shapes sparkling around it."]),
  (33, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["A bright green chlorella wave washes the toxins away.", "Tiny probiotic hero buddies rebuild the gut wall brick by brick.", "A spirulina hero flexes and shields the gut.", "Twenty little ingredient sparkles swirl through and the gut glows healthy."]),
  (37, "INT. KITCHEN — DAY", ["★ Peanut butter bag — his owner scoops the green powder from the bag into {the dog}'s bowl; {the dog} digs in happily."]),
  (38, "EXT. PARK — DAY, WEEKS LATER", ["{The dog} walks right past the grass and runs happily with his owner.", "His paws are clean and he isn't licking them."]),
  (40, "INT. GAME SHOW SET — BRIGHT", ["The meter behind {the dog} drops from red all the way down to green as he cheers."]),
  (41, X, ["The x-ray {the dog} again: his gut glows a calm healthy gold."]),
  (43, "INT. LIVING ROOM — GOLDEN HOUR", ["★ Peanut butter bag — {the dog} nudges the bag toward the camera with his nose; his owner smiles behind him."]),
 ],
}

# Song 3 v2 (Reed, 2 Nov: "more uniform" game show): every moment is rated on the set, then the camera pans to the show's
# mega screen and pushes through it into the real world. One set, described the same way every time. No x-ray.
SET = "INT. GAME SHOW SET — BRIGHT"
SETLOOK = ("the same bright game show studio: a glossy blue-and-gold stage ringed with marquee bulbs, the dog's gold host podium on the left, "
           "a second contestant podium on the right, a giant vertical one-to-ten meter glowing green to red at the side, and a huge curved mega screen behind")
SCREEN = "The camera pans to the mega screen behind him and pushes in until the screen fills the frame."
INTO = "We come through the glowing edge of the game show mega screen, which falls away as we land in the real world: "
SCENES["song3b"] = [
  (1,  SET, [f"Wide on {SETLOOK}.", "{The dog} stands at his host podium like a game show host, grinning, and the giant one-to-ten meter lights up behind him.", "On the mega screen, a crowd of dog owners shrug and smile, unbothered."]),
  (3,  SET, ["The meter flashes red and the marquee bulbs blink like an alarm.", "{The dog} fans out four blank scorecards in his paw and gives the camera a knowing look."]),
  (5,  SET, ["Round one: {the dog} at his podium slaps down a scorecard; close-up of the card showing a big number 4, and the meter jumps to 4.", SCREEN]),
  (7,  "EXT. PARK PATH — DAY", [INTO + "on a walk, {the dog} grazes on the grass like a lawnmower, his belly gurgling, looking queasy, then munches even more to settle it."]),
  (9,  SET, ["Round two: {the dog} squints at the camera from his podium and slaps down a scorecard; close-up of the card showing a big number 6, and the meter jumps to 6.", SCREEN]),
  (11, "INT. BEDROOM — MORNING", [INTO + "{the dog} wakes up in bed with crusty, glued-shut eyes and pries one open with his paw.", "Little grey specks drift out from the corners of his eyes."]),
  (13, SET, ["Round three: {the dog} slaps down a scorecard; close-up of the card showing a big number 8, and the meter jumps to 8 with a flash.", SCREEN]),
  (15, "INT. LIVING ROOM — DAY", [INTO + "{the dog} licks his paws in a tongue-blur frenzy on the rug.", "An angry red glow spreads under the fur of his paws and across his skin."]),
  (17, SET, ["Round four, the big one: a drumroll spotlight on {the dog}, who slaps down a scorecard; close-up of the card showing a big number 9, and the meter shoots up to 9, flashing red.", SCREEN]),
  (19, "INT. KITCHEN — DAY", [INTO + "his owner leans in to kiss {the dog}; his breath puffs out a green stink cloud that wilts the houseplant on the counter, and she reels back."]),
  (21, SET, ["His owner stands at the contestant podium, looking sheepish and confused, as the meter glows red behind her."]),
  (23, SET, ["{The dog} trots over to her podium and rests his head on her hand to comfort her.", "He holds up a scorecard with a big heart on it, and she smiles."]),
  (25, SET, ["The studio lights dim to a single spotlight on {the dog}, who leans toward the camera as if sharing a secret."]),
  (26, SET, ["The mega screen shows four glowing symptom icons — grass, an eye, a paw and a stink cloud — sliding together and merging into one glowing gut.", "{The dog} points up at the screen from his podium."]),
  (29, SET, ["A little conveyor belt rolls across the stage carrying dry kibble, a glass of tap water and artificial treats; each one gets a big red X on the mega screen.", "Then a healthy golden glow sweeps across the mega screen."]),
  (31, SET, ["★ Peanut butter bag — the grand prize: the stage turntable spins to reveal the bag under a spotlight, with golden five-star shapes sparkling on the mega screen and his owner clapping at her podium."]),
  (33, SET, ["The show's doors slide open and three cute ingredient heroes march onto the stage: a green chlorella wave buddy who splashes, tiny probiotic buddies carrying bricks, and a spirulina hero who flexes.", "{The dog} cheers from his podium."]),
  (36, "INSIDE THE DOG'S GUT — A CUTE ANIMATED WORLD", ["Through the mega screen into a cute animated world inside the dog's gut: the probiotic buddies set the last bricks, the green wave washes it clean and twenty little ingredient sparkles light it up a healthy gold."]),
  (37, "INT. KITCHEN — DAY", [INTO + "★ Peanut butter bag — his owner scoops the green powder from the bag into {the dog}'s bowl, and he digs in happily."]),
  (38, SET, ["Back on the set, weeks later: {the dog} tosses his old scorecards over his shoulder one by one as the meter drops segment by segment from red down to green."]),
  (40, "EXT. PARK — DAY, WEEKS LATER", [INTO + "{the dog} trots right past the grass and runs happily beside his owner, clean paws, tail wagging."]),
  (41, SET, ["The meter glows all green; {the dog} at his host podium gives the camera a wink, and confetti begins to fall."]),
  (43, SET, ["★ Peanut butter bag — the bag sits on the spinning turntable under a spotlight while the mega screen fills with a crowd of happy dogs and their owners."]),
  (44, "INT. LIVING ROOM — GOLDEN HOUR", [INTO + "{the dog} and his owner cuddle on the couch, both relaxed and happy; he's himself again."]),
  (45, SET, ["★ Peanut butter bag — {the dog} nudges the bag toward the camera with his nose from his podium as confetti falls; his owner smiles beside him."]),
]
DOGS["song3b"] = DOGS["song3"]

# Song 3 v3 (Reed, 2 Nov: the cards came before the sung score; "more emotion, more comedy"). Only the rounds and the
# pre-chorus are remade; each round follows the lyrics: the replay on the mega screen ("Number one, eating grass…"),
# the card landing on the sung number, then into the real world for the "because" lines. Spans are song seconds;
# the card clips start just before the sung number (four 19.14, six 29.72, eight 42.14, nine 54.74).
def CARD(n, extra=""):
    return ["Close-up on {the dog} at his gold host podium: he slams a white scorecard down facing the camera, one big bold black number " + n +
            " on it, clearly readable, and holds it there; the giant meter behind him jumps to " + n + extra + "."]
def REPLAY(replay, react):
    return ["Over the shoulder of {the dog} at his gold host podium: the game show mega screen plays a replay of " + replay, react]
SCENES["song3c"] = [
  ((15.6, 18.85), SET, REPLAY("him on a walk grazing on grass like a cow, while two real cows in the next field stare at him.", "{The dog} turns back to the camera, cringes and slowly facepalms with one paw.")),
  ((18.85, 20.08), SET, CARD("4")),
  ((20.08, 25.06), "EXT. PARK PATH — DAY", [INTO + "on a walk, {the dog} munches grass, his belly gurgles and he freezes, queasy and guilty, a blade of grass hanging from his mouth; his owner on the other end of the leash stares at him, baffled, palms up."]),
  ((25.06, 28.92), SET, REPLAY("him waking up with his eyes crusted shut and walking straight into the bedroom door frame with a bonk.", "{The dog} winces and covers his eyes with both paws.")),
  ((28.92, 30.30), SET, CARD("6")),
  ((30.30, 38.0), "INT. BEDROOM — SUNNY MORNING", [INTO + "his owner sits on the bed and gently wipes {the dog}'s crusty eyes with a warm cloth; he leans into her hand, eyes closed, comforted.", "Little grey specks drift away from the corners of his eyes."]),
  ((38.0, 41.2), SET, REPLAY("him licking his paws so fast his tongue is a blur, the rug soaked around him.", "{The dog} slowly hides both paws behind the podium and looks away, all innocence.")),
  ((41.2, 42.44), SET, CARD("8", ", and a red alarm light flashes")),
  ((42.44, 51.5), "INT. LIVING ROOM — NIGHT", [INTO + "at 2 a.m. his owner, in pajamas, flicks on a lamp and catches {the dog} mid-lick on the rug, tongue out, frozen like a burglar caught in the act.", "An angry red glow spreads under the fur of his paws and across his skin."]),
  ((51.5, 54.06), SET, REPLAY("his owner leaning in to kiss him and dramatically fainting backward onto the couch.", "Under a drumroll spotlight, {the dog} breathes into his paw, sniffs it, and his eyes water.")),
  ((54.06, 55.62), SET, CARD("9", ", red lights flash and a siren light spins")),
  ((55.62, 64.36), "INT. KITCHEN — DAY", [INTO + "{the dog} pants happily and his breath puffs a green stink cloud that wilts the houseplant on the counter; his owner pinches her nose with one hand but pulls him into a hug with the other, laughing."]),
  ((64.36, 73.18), SET, ["His owner stands alone at the contestant podium under the red glow of the meter, presses her buzzer and gives a guilty, embarrassed shrug.", "Then she covers her face with her hands, mortified, her shoulders slumping."]),
  ((73.18, 81.54), SET, ["{The dog} trots across the stage to her podium, rests his head on her hand and holds up a scorecard with a big red heart on it.", "Her eyes well up; she kneels and hugs him tight as warm golden light floods the stage."]),
]
DOGS["song3c"] = DOGS["song3"]

# Song 3 v4 (Reed, 2 Nov: the game-show hook doesn't read; make the dog a vlogger, keep the owner in most shots, she is the viewer).
# "Rating dog symptoms 1 to 10" is a creator format: the dog films himself on a phone; each symptom is named to camera, shown as
# "vlog footage" starring his owner, then rated with a crayon card on the sung number. Real-world clips from v2/v3 are reused (REUSE).
VLOG = "INT. LIVING ROOM — DAY, HIS VLOG CORNER"
VLOGLOOK = ("the same cozy living room vlog corner, seen as the phone's view: a phone on a small tripod with a ring light, a whiteboard on the wall "
            "behind, a grey couch, a houseplant, warm daylight")
CARDV = lambda n, her: ["In his vlog corner, {the dog} thrusts a crayon-drawn card with one big bold number " + n + " on it right up to the lens, clearly readable; " + her]
SCENES["song3d"] = [
  ((0.0, 3.34), VLOG, [f"In {VLOGLOOK}: {{the dog}} taps record on the phone, the ring light flicks on, and he leans into the lens grinning like a creator."]),
  ((3.34, 7.06), VLOG, ["Behind {the dog}, his owner wanders past in pajamas eating a bowl of cereal and gives the camera a casual, unbothered shrug."]),
  ((7.06, 12.24), VLOG, ["{The dog} slaps four doodles onto the whiteboard one after another: a grass blade, a crusty eye, a paw and a stink cloud.", "On the couch his owner chokes on her coffee and stares."]),
  ((12.24, 15.6), VLOG, ["{The dog} points a paw at himself with a knowing look; his owner, beside him, gives the camera a slow side-eye."]),
  ((15.6, 18.85), "EXT. PARK — DAY", ["Vlog footage: on a walk {the dog} grazes on the grass like a cow while two real cows over the fence stare at him; his owner tugs the leash and pleads with him, embarrassed."]),
  ((18.85, 20.08), VLOG, CARDV("4", "behind him his owner facepalms.")),
  ((20.08, 25.06), "REUSE v3 c3", []),
  ((25.06, 28.92), "INT. BEDROOM — MORNING", ["Vlog footage: {the dog} wakes up with his eyes crusted shut and walks straight into the door frame with a bonk; his owner rushes in, wincing."]),
  ((28.92, 30.3), VLOG, CARDV("6", "behind him his owner winces and covers her mouth.")),
  ((30.3, 38.0), "REUSE v3 c6", []),
  ((38.0, 41.2), VLOG + " — FOOTAGE", ["Vlog footage: {the dog} licks his paws so fast his tongue is a blur, the rug soaked around him; on the couch his owner lifts her feet away from the wet patch, horrified."]),
  ((41.2, 42.44), VLOG, CARDV("8", "behind him his owner buries her face in her hands.")),
  ((42.44, 51.5), "REUSE v3 c9", []),
  ((51.5, 54.06), VLOG + " — FOOTAGE", ["Vlog footage: his owner leans in to kiss {the dog} on the couch, gets a whiff of his breath and faints dramatically backward onto the cushions."]),
  ((54.06, 55.62), VLOG, CARDV("9", "behind him his owner pinches her nose shut.")),
  ((55.62, 64.36), "REUSE v3 c12", []),
  ((64.36, 73.18), VLOG, ["{The dog} swings the phone camera around to his owner on the couch; she waves at the lens sheepishly, then hides her face in a cushion, embarrassed."]),
  ((73.18, 81.54), VLOG, ["{The dog} hops up on the couch beside her and rests his head in her lap; she lowers the cushion, her eyes welling up, and hugs him tight, both in the phone's frame."]),
  ((81.54, 86.96), VLOG, ["{The dog} and his owner lean into the lens together, as if sharing a secret with the viewer."]),
  ((86.96, 95.56), VLOG, ["At the whiteboard {the dog} draws big arrows from the four doodles into one big gut doodle in the middle.", "His owner gasps and points at it."]),
  ((95.56, 102.22), VLOG, ["His owner guiltily pulls a bag of dry kibble, a glass of tap water and a jar of artificial treats from behind her back.", "{The dog} sweeps them off the table into a bin and draws a heart around the gut doodle."]),
  ((102.22, 108.82), VLOG, ["★ Peanut butter bag — his owner does an unboxing to the camera: she opens a parcel and lifts the bag to the lens as golden five-star sparkles burst around it; {the dog}'s jaw drops."]),
  ((108.82, 119.8), VLOG, ["At the vlog desk {the dog} presents three little toy figures to the lens like a tier list while his owner holds each one up: a green chlorella wave buddy that splashes, tiny probiotic buddies stacking bricks, and a muscly spirulina hero that flexes."]),
  ((119.8, 124.72), "REUSE v2 c18", []),
  ((124.72, 129.1), "REUSE v2 c19", []),
  ((129.1, 136.5), VLOG, ["Weeks later: his owner wipes the four doodles off the whiteboard one by one.", "{The dog} huffs his breath in her face; she sniffs, then beams and gives a big thumbs up."]),
  ((136.5, 142.18), "REUSE v2 c21", []),
  ((142.18, 148.76), VLOG, ["{The dog} and his owner sit side by side facing the lens; she looks into the camera and nods knowingly, and he winks."]),
  ((148.76, 153.52), VLOG, ["★ Peanut butter bag — his owner holds the bag up to the lens while {the dog} points his paw down, toward the link below."]),
  ((153.52, 158.0), "REUSE v2 c24", []),
  ((158.0, 165.44), VLOG, ["★ Peanut butter bag — {the dog} nudges the bag toward the lens with his nose while his owner looks straight into the camera and smiles.", "Then {the dog} reaches up and taps the phone to stop recording."]),
]
DOGS["song3d"] = DOGS["song3"]
REUSE3D = {"v3": {"c3": 0.4, "c6": 0.7, "c9": 0.2, "c12": 0.8}, "v2": {"c18": 0.0, "c19": 0.0, "c21": 0.0, "c24": 0.2}}

# Song 3 hook v5 (Reed, 2 Nov: the vlog had too much going on; redo the game show's hook). One clear action per sung line,
# on the v3 set, the owner in it; cut in front of v3 from 15.6 s.
SCENES["song3e"] = [
  ((0.0, 3.34), SET, [f"Wide on {SETLOOK}.", "{The dog} stands at his gold host podium, grinning, as the giant meter beside him lights up step by step from 1 at the bottom to 10 at the top."]),
  ((3.34, 7.06), SET, ["His owner stands at the contestant podium, relaxed, and waves it off with an easy smile and a shrug, as if it's all perfectly normal."]),
  ((7.06, 12.24), SET, ["The giant meter flashes red and an alarm light spins; his owner's smile drops and she stares up at it, shocked."]),
  ((12.24, 15.6), SET, ["{The dog} fans out four scorecards toward the camera in his paw and gives a slow, knowing look."]),
]
DOGS["song3e"] = DOGS["song3"]

def script(song):
    dog = DOGS[song][0]; the, The = f"the {dog}", f"The {dog}"; out = []
    for n, (first, place, lines) in enumerate([x for x in SCENES[song] if not x[1].startswith("REUSE")], 1):
        out.append(f"SCENE {n} — {place}")
        out += [l.replace("{the dog}", the).replace("{The dog}", The) for l in lines]; out.append("")
    return "\n".join(out).strip() + "\n"

if __name__ == "__main__":
    for s in SCENES: open(f"{s}-script.txt", "w").write(script(s))
