"""The two narrated Iron Paws ads: one plan, two dogs. Each scene: (first narration sentence, place, action lines, shared?).
Shared scenes have no dog or face in them, so the Frenchie video reuses the pit bull video's clips."""
SCENES = [
 (1,  "STUDIO — DEEP BLUE BACKDROP", ["A translucent x-ray view of {the dog}: the skeleton glows softly, and three hot spots flash glowing red-orange one by one: a paw, the skin of the back, an ear."], False),
 (2,  "INT. LIVING ROOM — DAY", ["His owner walks past {the dog} licking his paw on the rug, smiles without looking twice and gives him a quick pat.", "{The dog} scratches behind his ear while she carries on, unbothered.", "Close on {the dog}'s face: big pleading eyes looking up, ears pulled back, asking for help."], False),
 (5,  "INT. BEDROOM — NIGHT, 2 A.M.", ["The bedside clock glows 2:00. His owner sleeps peacefully while {the dog}, at the foot of the bed, licks his paws over and over in the blue moonlight."], False),
 (6,  "INT. LIVING ROOM — EVENING", ["In the corner of the living room {the dog} shakes his head hard, ears flapping, while his owner on the couch scrolls through her phone, not noticing."], False),
 (7,  "EXT. BACKYARD — DAY", ["In the backyard grass {the dog} scratches at his skin with a back leg, frantic.", "Through the kitchen window his owner watches him, worried, a spray bottle in her hand, wondering what to try next."], False),
 (8,  "INT. LIVING ROOM — DAY", ["{The dog} sits and looks straight into the camera, trying to say something.", "A box of allergy pills slides away out of frame.", "{The dog} tilts his head, as if to say no, it's not that."], False),
 (12, "STUDIO — DEEP BLUE BACKDROP", ["The x-ray view of {the dog}: the camera pushes into his glowing belly.", "Inside the gut, little balanced good-bacteria orbs tip over and scatter; red inflammation sparks rise and yellow yeast blobs start to multiply."], False),
 (14, "STUDIO — DEEP BLUE BACKDROP", ["On the x-ray {the dog}, red inflammation glow spreads out across his skin.", "Yellow yeast glow climbs up into his ears.", "Everything pushes outward from his belly to every surface of his body, glowing at the paws, the skin and the ears."], False),
 (17, "STUDIO — DEEP BLUE BACKDROP", ["Quick push-ins on the x-ray {the dog}: his paw glows red, then the skin of his back, then his ear.", "Pull back: three glowing lines connect the paw, the skin and the ear to one red, flickering gut at the centre."], False),
 (22, "INT. LIVING ROOM — EVENING", ["His owner scrolls through her phone on the couch, {the dog} beside her, then suddenly looks up with a surprised expression: she finally figured it out.", "She sits up with new determination and looks at {the dog}."], False),
 (24, "INT. KITCHEN COUNTER — DAY", ["Five natural ingredients appear one by one on the kitchen counter in little glass jars: probiotic capsules, green chlorella tablets, blue-green spirulina powder, a chicory root and a burdock root.", "Her hands slide the old sprays and creams aside and keep the natural ingredients."], True),
 (26, "INT. KITCHEN — DAY", ["His owner is buried in five jars, a kitchen scale, measuring spoons and scribbled notes, green powder spilled, frustrated.", "She pushes it all aside, picks up the Iron Paws bag and shows it to {the dog}, who sniffs it eagerly.", "★ Peanut butter bag — she holds the bag, label toward camera."], False),
 (29, "INT. KITCHEN COUNTER — DAY", ["★ Peanut butter bag — hero shot of the bag on the counter, label to camera.", "Glowing icons of the five ingredients and many more little ingredients swirl out of the bag and around it."], True),
 (30, "INT. KITCHEN — DAY", ["★ Peanut butter bag — one scoop of green powder from the bag goes into {the dog}'s food bowl and is mixed in; {the dog} digs in happily."], False),
 (31, "INT. LIVING ROOM — DAY, WEEKS LATER", ["Weeks later, {the dog} rests calmly on the rug, paws clean, not licking.", "He gives one lazy stretch instead of scratching.", "No head shaking: his ears sit still and relaxed.", "Then he springs up and does joyful zoomies around the living room with a toy, acting years younger, while his owner laughs."], False),
 (36, "STUDIO — DEEP BLUE BACKDROP", ["The x-ray {the dog} again: the hot spots on the paws, skin and ears fade away, and his gut glows a calm, healthy gold."], False),
 (38, "INT. KITCHEN COUNTER — DAY", ["★ Peanut butter bag — the bag on the counter as golden five-star shapes rain down around it, glittering."], True),
 (39, "INT. LIVING ROOM — GOLDEN HOUR", ["His owner kneels and hugs {the dog}, both content.", "★ Peanut butter bag — {the dog} nudges the bag toward the camera with his nose and looks into the lens."], False),
]

def script(dog):
    the, The = f"the {dog}", f"The {dog}"
    out = []
    for n, (first, place, lines, shared) in enumerate(SCENES, 1):
        out.append(f"SCENE {n} — {place}")
        out += [l.replace("{the dog}", the).replace("{The dog}", The) for l in lines]
        out.append("")
    return "\n".join(out).strip() + "\n"

if __name__ == "__main__":
    for dog, f in (("pit bull", "video1-pitbull-script.txt"), ("Frenchie", "video2-frenchie-script.txt")):
        open(f, "w").write(script(dog))
