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

def script(song):
    dog = DOGS[song][0]; the, The = f"the {dog}", f"The {dog}"; out = []
    for n, (first, place, lines) in enumerate(SCENES[song], 1):
        out.append(f"SCENE {n} — {place}")
        out += [l.replace("{the dog}", the).replace("{The dog}", The) for l in lines]; out.append("")
    return "\n".join(out).strip() + "\n"

if __name__ == "__main__":
    for s in SCENES: open(f"{s}-script.txt", "w").write(script(s))
