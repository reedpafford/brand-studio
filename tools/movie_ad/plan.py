"""Movie Ad 1 (RP5), all three hook variations: who is in it, the pictures, and every clip as it
is sent to Seedance 2.5 through KIE. The script's spoken words are unchanged. Each prompt is
laid out as the tested clips were (Higgsfield's lesson shape): scene context, what each picture
is for, timed shots with who is in frame and who speaks, one look line, one sound line.
In a prompt, {paige} etc. become that picture's [ImageN] tag (film.py works out the numbers)."""

BRAND = 8
ALARM = 54  # the brand's product: the real Palace Guard alarm

CAST = {  # name on the site, then the words Seedream draws the sheet from
    "paige": ("Paige (RP5)", "A fictional 18-year-old girl, tall and athletic, with long dark brown hair in a high ponytail and a few flyaway strands, natural unretouched skin with faint freckles and no makeup. She wears a navy crewneck sweatshirt with a small white volleyball outline on the chest, black leggings and white sneakers."),
    "dana": ("Dana (RP5)", "A fictional woman in her mid-40s with shoulder-length dark brown hair pulled back in a loose clip, a tired, warm face, natural unretouched skin with fine lines and no makeup. She wears a long oatmeal knit cardigan over a grey t-shirt, black leggings and grey house slippers."),
    "mig": ("Man in gray (RP5)", "A fictional man in his mid-30s with a solid build, short dark brown hair and a short beard, natural unretouched skin, a flat expression. He wears a plain light-grey crewneck sweatshirt, matching grey sweatpants and scuffed tan lace-up work boots."),
    "officer": ("Officer (RP5)", "A fictional male police officer in his 40s with short greying hair and a clean-shaven weathered face. He wears a dark navy short-sleeved patrol uniform with a plain metal badge and blank shoulder patches, a black duty belt and black boots."),
    "manager": ("Store manager (RP5)", "A fictional woman in her 50s, a store manager, with chin-length grey-blonde hair, reading glasses pushed up on her head and a soft build. She wears a plain red polo shirt with a blank white name badge, khaki trousers and black flat shoes."),
    "det": ("Detective (RP5)", "A fictional man in his late 50s, a detective, flat and quiet: thinning grey hair, deep-set tired eyes, a heavy lined face, clean-shaven. He wears a rumpled charcoal sport coat over a pale blue open-collar shirt, dark trousers and brown leather shoes, with a small plain badge clipped at his belt."),
    "stroller": ("Woman with the stroller (RP5)", "A fictional woman in her early 30s with blonde hair in a messy bun and natural unretouched skin. She wears a black quilted vest over a long-sleeved grey top, blue jeans and running shoes."),
    "kid": ("Cart kid (RP5)", "A fictional lanky 19-year-old young man with curly brown hair, a store cart attendant. He wears a red polo shirt under a yellow high-visibility vest, khaki trousers and black sneakers."),
}

PICTURES = {  # places and things with no face: drawn once, then attached by file
    "checkout": "An empty photographic view of the self-checkout area of a big-box store in the evening: a row of four self-checkout kiosks with scanners and bagging shelves on the left, a low metal rail, polished grey concrete floor, and the store's aisles receding behind. Camera at 1.4 metres from the end of the row, a three-quarter view along the kiosks, 35mm lens, the nearest kiosk soft at the left edge. Cool overhead fluorescent tubes, darker aisles behind, red accents on the kiosk ends. Real scuffed plastic and steel. No people, no readable text, no logos.",
    "lot": "An empty photographic view of the back half of a big-box store parking lot at dusk: wet dark asphalt with painted bay lines, a deep blue sky, tall lot lamps just on and one lamp overhead half out and flickering. One silver compact hatchback is parked alone at centre-right, its driver's side facing the camera; three empty bays to its left. The store's long lit front sits far in the background with no readable signs, a cart corral at mid-distance. Camera at 1.4 metres, a three-quarter view from behind the car's rear-left corner, 35mm lens, open asphalt in the foreground. Mild grain, real wet-asphalt and car-paint texture. No people, no text, no logos.",
    "van": "A photograph of one white windowless cargo van parked on wet asphalt at dusk, seen three-quarter from the front-left: no side or rear windows, plain white panels with a little road grime, steel wheels, headlights off, its sliding side door fully open onto a dark empty interior. Camera at 1.4 metres, 35mm lens, the whole van in frame with space around it, a deep blue sky and distant lot lamps behind. No people, no text, no logos, a blank licence plate.",
    "kitchen": "An empty photographic view of a lived-in family kitchen just after sunset: white shaker cabinets, a butcher-block counter with a mixing bowl, a wooden spoon and an oven mitt, a stainless oven with its display glowing, a fridge with magnets and a child's drawing. Warm light from a pendant lamp over the counter and the oven's glow; a deep blue window over the sink. Camera at 1.3 metres from the corner by the doorway, a three-quarter view along the counter, 35mm lens, a chair back soft near the lens. Real wear on the cabinet edges, crumbs on the counter. No people, no readable text, no logos.",
    "table": "An empty photographic view of the same family kitchen on a grey afternoon, seen from the hallway: a round oak kitchen table with four chairs by a window on the left, a full mug of coffee and a closed laptop on it; white shaker cabinets and a butcher-block counter behind; on the right an open doorway to a hall with a carpeted staircase and white banister rising out of frame. Soft grey daylight from the window, the hall darker. Camera at 1.3 metres from the hallway corner, 35mm lens, the stair banister soft at the right edge near the lens. Real wear, a dish towel on a chair. No people, no readable text, no logos.",
}

VOICE = {
    "paige": "Paige is a girl of 18, light and clear, a little dry",
    "dana": "Dana is a woman in her 40s, warm and slightly husky",
    "officer": "the officer is a man in his 40s, low and even",
    "det": "the detective is a man in his late 50s, low, flat and quiet, unhurried",
    "manager": "the manager is a woman in her 50s, bright and polite",
    "mig": "the man in gray is a man in his 30s, low and casual",
    "stroller": "the woman with the stroller is in her 30s, fast and breathless",
    "kid": "the cart kid is a young man of 19, loud, his voice cracking",
}

WHO = {"paige": "Paige", "dana": "Dana", "officer": "the officer", "det": "the detective", "manager": "the manager",
       "mig": "the man in gray", "stroller": "the woman with the stroller", "kid": "the cart kid"}

JOB = {  # what each picture is for, said once per clip
    "paige": "{paige} is Paige: her face, hair and outfit.",
    "dana": "{dana} is Dana, Paige's mother: her face, hair and outfit.",
    "mig": "{mig} is the man in gray: his face, hair and outfit.",
    "officer": "{officer} is the officer: his face and uniform.",
    "manager": "{manager} is the store manager: her face, hair and red shirt.",
    "det": "{det} is the detective: his face, hair and clothes.",
    "stroller": "{stroller} is the woman with the stroller: her face, hair and outfit.",
    "kid": "{kid} is the cart kid: his face, hair and uniform.",
    "alarm": "{alarm} is the alarm on Paige's keys, shown exactly as it is: a slim white pill-shaped personal alarm with a ring on top, about the length of a car key.",
    "store": "{store} is the store: use it for the place, its light and colour, not for framing.",
    "checkout": "{checkout} is the self-checkout: use it for the place, its light and colour, not for framing.",
    "lot": "{lot} is the parking lot and Paige's silver car: use it for the place, the car, the light and the colour, not for framing.",
    "lotnight": "{lotnight} is the same parking lot later, at night under police lights, with Paige's car: use it for the place, the car, the light and the colour, not for framing.",
    "van": "{van} is the white van: no windows, its side door open.",
    "kitchen": "{kitchen} is Dana's kitchen: use it for the place, its light and colour, not for framing.",
    "table": "{table} is the kitchen table and the stairs behind it: use it for the place, its light and colour, not for framing.",
}

DRAMA = "photoreal TV-drama footage, long lens, shallow focus, the acting small and real"
END = "No music, no subtitles."
GREY2 = "a second man in the same gray sweatsuit and tan boots, shaved head, heavier"
GREY3 = "a third man in the same gray sweatsuit and tan boots, tall and thin, in a gray knit cap"


def clip(seconds, refs, context, shots, look, sound, voices=(), extra=()):
    return {"seconds": seconds, "refs": list(refs), "context": context, "shots": list(shots),
            "look": look, "sound": sound, "voices": list(voices), "extra": list(extra)}


CLIPS = {
# ---------------------------------------------------------------- the three hooks
"h1": clip(15, ["stroller", "kid", "paige", "alarm", "lot", "van"],
    "Dusk in a big-box store parking lot, seconds after an attempted abduction. A personal alarm is screaming and its white strobe flashes across the lot. A white windowless van pulls away with its side door still open. A woman with a stroller runs with her phone to her ear, a cart attendant chases the van, and Paige stands frozen over a carton of broken eggs with the alarm in her fist.",
    ["Shot 1, 0-5 s: low wide from between two parked cars, a bumper soft near the lens, camera still. The white van swings away toward the exit on the right, its side door open, white strobe light flashing across it. The woman with the stroller runs in from the left, pushing the stroller one-handed, phone at her ear. She shouts into the phone: \"Two men just tried to abduct a girl in the Target parking lot! They're in a white van, it's leaving!\"",
     "Shot 2, 5-8 s: handheld, tracking beside the cart kid at shoulder height as he sprints after the van with his phone held up, filming it. The cart kid alone in frame. He yells: \"I got the plate! I got it!\"",
     "Shot 3, 8-11 s: close on Paige's right fist at her side, gripping her keys and the alarm, its light pulsing white; a crushed egg carton and broken eggs on the asphalt by her white sneakers. The camera tilts up with the strobe to her face: eyes wide, lips parted, not moving.",
     "Shot 4, 11-15 s: medium two-shot, camera still. Paige on the right, frozen, the alarm still flashing in her fist. The woman with the stroller reaches her on the left and puts a hand on her arm, phone still at her ear. She says into the phone, catching her breath: \"She's okay. She's standing right here. They almost got her.\" Hold on Paige's face for the last second."],
    f"{DRAMA}, dusk, a deep blue sky, lot lamps just on, white strobe flashes on wet asphalt.",
    "The alarm's siren screams through the whole clip, under the voices; an engine pulling away, running footsteps.",
    ["stroller", "kid"]),

"h2": clip(14, ["dana", "kitchen"],
    "Just after sunset in a family kitchen. The oven beeps. Dana's phone buzzes on the counter with a call from her daughter Paige; she answers expecting Paige, and a police officer tells her three men just tried to abduct her daughter. Dana slides down the cabinet to the kitchen floor.",
    ["Shot 1, 0-2.5 s: close insert at counter height, camera still. A phone lies on the butcher-block counter beside a mixing bowl; it buzzes and its screen lights with an incoming call, the name \"Paige\" on it. Dana's hand comes in and picks it up. An oven beeps twice.",
     "Shot 2, 2.5-5 s: medium close-up of Dana at the counter, camera still, a chair back soft near the lens. Phone at her ear, half smiling, wiping her free hand on a dish towel. Dana says, easy: \"Hey, did you get the eggs?\"",
     "Shot 3, 5-11 s: close-up of Dana, a slow push in to her eyes. A man's voice comes through the phone, thin and filtered, steady: \"Ma'am, this is the police. Your daughter's safe, she's with me. Three men just tried to abduct her in the Target parking lot.\" Her smile goes; the hand with the towel stops; her eyes fix on nothing. Her lips stay closed while he speaks.",
     "Shot 4, 11-14 s: low angle from the floor, camera still. Dana's back slides down the cabinet door until she sits on the kitchen floor, the phone still at her ear. Dana says, barely a voice: \"Oh my god, my baby.\""],
    f"{DRAMA}, warm lamp light on her face, the deep blue window behind, the background darker.",
    "The officer is heard only through the phone, thin and filtered: a man in his 40s, low and even. A phone buzzing on wood, the oven's beep, the fridge's hum.",
    ["dana"]),

"h3": clip(16, ["paige", "mig", "lot", "van"],
    "Dusk at the front of a big-box store. Paige walks out to the parking lot with a grocery bag and her keys. Inside the glass doors a man in gray watches her go and phones it in. Out in the lot a white windowless van turns its lights on and rolls up near her car with its side door already open; two men get out and walk straight at her. She tries to scream and nothing comes out.",
    ["Shot 1, 0-3 s: from inside the store, over the man in gray's shoulder, soft near the lens, looking out through the glass doors, camera still. Paige walks away into the lot, a plastic grocery bag in her left hand, her keys in her right.",
     "Shot 2, 3-9 s: close on the man in gray behind the glass, lot lamps reflected on it, camera still. Phone at his ear, his eyes following her. The man in gray alone in frame. He says into the phone: \"Yo, boss, I've got our next target. The tall one in the volleyball sweatshirt. She's parked in the back half of the lot.\"",
     "Shot 3, 9-11 s: wide down a row of parked cars, camera still. At the far end the white van's headlights snap on.",
     f"Shot 4, 11-14 s: medium from behind Paige's right shoulder, soft near the lens, three steps from her silver car, camera still. The van stops three bays away, its side door already open, dark inside. Two men step out and walk straight toward her, unhurried: {GREY2}, and {GREY3}.",
     "Shot 5, 14-16 s: close-up of Paige, camera still. Her mouth opens to scream and no sound comes out. End on her open mouth."],
    f"{DRAMA}, dusk, a deep blue sky, lot lamps just on, the store's glow behind.",
    "Automatic doors, a quiet lot, an engine idling, slow boots on asphalt; total silence in the last shot.",
    ["mig"]),

# ---------------------------------------------------------------- the body
"b1": clip(25, ["paige", "mig", "store"],
    "A Tuesday evening in a big-box store. A few ordinary shoppers push trolleys and carry baskets, going about their evening. Paige shops with a red basket on her forearm, a gallon of milk in it. One by one she notices three men in identical gray sweatsuits and work boots drifting around her aisles: everyone else has a trolley or a basket, and they have nothing. They never walk toward her, only past. Her thoughts are heard as a voice-over; her lips stay closed all through.",
    ["Shot 1, 0-3 s: medium close-up at eye height, past the soft edge of the egg cooler near the lens, camera still. Paige alone in frame, on the left, side-on to the cooler, lifting a carton of eggs; her hand stops and her eyes rise toward the far end of the aisle.",
     "Shot 2, 3-6 s: long-lens shot down the aisle between two shelf ends, camera still. The man in gray alone in frame, small at the far end and off to the right, hands in his pockets, no cart, looking toward the camera; his eyes snap away to a shelf too fast. Paige's thought is heard, flat and dry: \"Weird. But whatever.\"",
     f"Shot 3, 6-9 s: medium shot tracking beside Paige as she walks the main aisle, the basket on her forearm. A woman with a full trolley passes behind her. Paige's head turns to a side aisle: in it stands {GREY2}, side-on to a shelf, nothing in his hands.",
     f"Shot 4, 9-13 s: wide from a corner along the freezer wall, past a glowing freezer door near the lens, camera still. {GREY3} stands by the freezer doors, hands in his pockets, opening nothing, while a father and a small boy choose ice cream at the next door; Paige crosses the foreground, glancing at him. Her thought is heard, easy and quick: \"Construction guys, probably. I bet they're just on a break.\"",
     "Shot 5, 13-17 s: low wide from the corner of the cereal aisle, past a shelf end of cereal boxes soft near the lens, camera still. Paige walks away from us down the aisle, small, on the left; at the far cross-aisle a man in a gray sweatsuit walks past from left to right without looking in.",
     "Shot 6, 17-20 s: high angle over her shoulder into the basket, camera still. Paige has stopped. A gallon of milk and a carton of eggs in the red basket; her fingers tighten on the handle.",
     "Shot 7, 20-22 s: medium-wide over Paige's right shoulder, her shoulder soft near the lens, camera still. At the far cross-aisle three men in gray sweatsuits stand spread apart, side-on, arms hanging, nothing in their hands, while a shopper with a trolley walks between them without a glance. None of the three moves toward her.",
     "Shot 8, 22-25 s: close-up of Paige from the front-left, a slow push in to her eyes as they lift from the basket to the far end and stay there; a tight swallow. Her thought is heard, quiet and slow: \"Wait. Nobody's buying anything.\""],
    f"{DRAMA}, cool fluorescent tubes overhead, the aisle ends darker.",
    "Fluorescent hum, freezer compressors, sneakers and slow boots on concrete, a distant checkout beep. The voice-over is Paige's inner voice; nobody speaks aloud.",
    ["paige"]),

"b2": clip(10, ["paige", "manager", "checkout"],
    "The same evening at the store's self-checkout. A manager in a red shirt stands ten feet away reading a clipboard. Paige looks at her, almost says something, and doesn't.",
    ["Shot 1, 0-3 s: wide from the end of the kiosk row, the nearest kiosk soft at the left edge, camera still. Paige stands at a kiosk in the middle with her red basket; ten feet beyond her the manager reads a clipboard. Paige looks over at her. Two people in frame.",
     "Shot 2, 3-5 s: medium close-up of the manager, camera still. She looks up from the clipboard with a polite smile. The manager says: \"Find everything okay?\"",
     "Shot 3, 5-8 s: close-up of Paige, camera still. She glances back toward the aisles, holds it a beat, then turns back. Paige says, small: \"Yeah. Thanks.\"",
     "Shot 4, 8-10 s: close insert, camera still. Paige's hand slides the egg carton across the scanner glass; a red light, one beep. Behind, out of focus, the manager goes back to her clipboard."],
    f"{DRAMA}, cool fluorescent light, red accents on the kiosks.",
    "Scanner beeps, a plastic bag rustling, store hum.",
    ["manager", "paige"]),

"b3": clip(7, ["dana", "kitchen"],
    "At home at the same minute, just before dark. Dana checks her phone: her daughter's dot sits in the store parking lot, right where it should be. She puts the phone down and turns the oven on.",
    ["Shot 1, 0-2.5 s: close insert over Dana's hand, camera still. Her phone shows a map with one blue dot on a large parking lot. No readable words on the screen.",
     "Shot 2, 2.5-5 s: medium close-up of Dana at the counter, camera still, a chair back soft near the lens. She smiles at the phone. Dana says, sing-song: \"Oop! There you are.\"",
     "Shot 3, 5-7 s: close on her hands, camera still. She sets the phone face down on the butcher-block counter and turns the oven dial; the oven display lights."],
    f"{DRAMA}, warm lamp light, the window going blue.",
    "A quiet kitchen, the oven's click and one beep.",
    ["dana"]),

"b4": clip(21, ["paige", "mig", "alarm", "lot", "van"],
    "The back half of the parking lot at dusk, under a lamp that is half out. Paige walks to her silver car with her keys in her right hand and a grocery bag in her left. A white windowless van rolls up and stops three bays away with its side door already open. Two men get out and walk straight at her without hurrying. She freezes: her thoughts are heard as a voice-over while her lips make no sound. Her thumb finds the alarm on her keys.",
    ["Shot 1, 0-3 s: low wide past a parked car's bumper soft near the lens, camera still. Paige walks left to right toward her silver car under the flickering lamp, keys in her right hand, the bag in her left.",
     "Shot 2, 3-6 s: over Paige's right shoulder, three steps from her car door, camera still. The white van rolls in and stops three bays away, its side door already open, dark inside. Her thought is heard, quiet: \"Why is the door already open?\"",
     f"Shot 3, 6-10 s: medium, camera still, at her eye height. The man in gray and {GREY2} step out of the van and walk straight toward the camera, not hurrying. The man in gray says, friendly and flat: \"Hey. Hey, you dropped something.\"",
     "Shot 4, 10-13 s: close-up of Paige, camera still. Her eyes drop to her hands and come back up. Her thought is heard: \"I didn't drop anything.\" Her mouth opens and nothing comes out.",
     "Shot 5, 13-17 s: tighter close-up, a slow push in to her eyes. Her mouth stays open, silent; her breath stops. Her thought is heard, faster: \"Scream. Just scream. Why can't I scream?\"",
     "Shot 6, 17-21 s: extreme close-up of her right hand, camera still. Among her keys, her thumb slides onto the white alarm and hooks the ring at its top. Her thought is heard, urgent: \"The thing on my keys. Pull it.\" End on her thumb in the ring."],
    f"{DRAMA}, dusk, a deep blue sky, one flickering lamp overhead, the van's dark doorway.",
    "A quiet lot: an engine idling, slow boots on asphalt, the lamp's buzz. The voice-over is Paige's inner voice; only the man in gray speaks aloud.",
    ["paige", "mig"]),

"b5": clip(21, ["paige", "mig", "kid", "stroller", "alarm", "lot", "van"],
    "The same moment in the parking lot at dusk, a dozen ordinary shoppers scattered across it going about their evening. Paige drops her eggs and pulls the ring out of the top of her alarm: a loud siren screams across the lot and its strobe flashes white on the van. Everyone in the lot turns to look. The two men stop, look at each other, and walk back to the van as if they forgot something; it pulls out with its side door still open. The cart kid runs after it with his phone up. Paige gets into her car and locks the doors.",
    ["Shot 1, 0-2 s: low close insert at asphalt level, camera still. An egg carton lands and bursts open; yolk and shells across the wet asphalt.",
     "Shot 2, 2-5.5 s: close on Paige's hands at chest height, camera still. Her left hand grips the white body of the alarm; two fingers of her right hand are hooked through the round ring at its top. She pulls the ring straight up and it comes out of the body: the ring is now in her right hand with her keys hanging from it, apart from the white body in her left. At once the round lens on the body fires a hard white strobe and a loud siren starts.",
     "Shot 3, 5.5-8.5 s: wide across the lot from a low corner, a cart corral soft near the lens, camera still. A dozen shoppers scattered across the lot all turn their heads toward the sound at once: a man at his open car boot, a couple pushing a full trolley, two teenagers by a pickup, the cart kid behind a line of carts, and the woman with the stroller, who stops so fast the stroller rolls a foot ahead of her.",
     f"Shot 4, 8.5-12 s: medium on the two men, the strobe pulsing white on them, camera still. The man in gray and {GREY2} stop mid-step, look at each other, then turn and walk back toward the van without a word.",
     "Shot 5, 12-16 s: wide, camera still. The white van pulls out toward the exit with its side door still open. The cart kid lets go of his carts and sprints after it with his phone held up. The cart kid yells: \"I got the plate! I got it!\"",
     "Shot 6, 16-21 s: through the windscreen of Paige's car, camera still. Paige drops into the driver's seat, pulls the door shut, the locks clunk, and she holds her keys against her chest with both hands, breathing hard, the strobe still pulsing on her face. Paige alone in frame. Hold."],
    f"{DRAMA}, dusk, hard white strobe flashes on wet asphalt and on the white van.",
    "The alarm's siren screams from shot 2 to the end, muffled inside the car in the last shot; an engine pulling away, running footsteps, car locks.",
    ["kid"]),

"b6": clip(18, ["dana", "kitchen"],
    "Just after sunset in the kitchen. The oven beeps. Dana's phone buzzes on the counter with a call from Paige. She answers and cannot make out her daughter's crying; then a police officer comes on the line. Dana slides down the cabinet to the floor, then runs out of the front door in her slippers.",
    ["Shot 1, 0-3 s: close at counter height, camera still. The phone buzzes on the butcher-block counter, the name \"Paige\" on its screen; the oven beeps. Dana picks it up into a medium close-up. Dana says, easy: \"Hey, did you get the eggs?\"",
     "Shot 2, 3-7 s: medium close-up of Dana, camera still, a chair back soft near the lens. Through the phone, a girl's broken crying, no words. Dana's smile drops; she presses the phone closer. Dana says: \"Baby, slow down. I can't understand you.\"",
     "Shot 3, 7-13 s: close-up of Dana, a slow push in to her eyes. A man's voice comes through the phone, thin and filtered, steady: \"Ma'am, this is the police. Your daughter's safe, she's with me. Three men just tried to abduct her in the Target parking lot.\" Her lips stay closed while he speaks; her back finds the cabinet and she slides down it out of the bottom of the frame.",
     "Shot 4, 13-16 s: low angle from the floor, camera still. Dana sits on the kitchen floor against the cabinet, phone at her ear. Dana says, already getting up: \"I'm coming. Tell her I'm coming.\"",
     "Shot 5, 16-18 s: wide from the hallway, camera still. Dana runs out of the front door in her grey slippers and leaves it open; the oven still glowing behind."],
    f"{DRAMA}, warm lamp light on her face, the deep blue window behind, the background darker.",
    "The crying and the officer are heard only through the phone, thin and filtered; the officer is a man in his 40s, low and even. The oven's beep, a phone buzzing on wood, slippers on tile, a door.",
    ["dana"]),

"b7": clip(22, ["paige", "dana", "officer", "manager", "lotnight"],
    "Night in the store parking lot, twenty minutes later, under flashing police lights. Paige sits in the driver's seat of her parked car with the window down while an officer questions her. Her mother Dana runs in and holds her face; the store manager walks up and admits there were complaints for two weeks, and Dana turns on her.",
    ["Shot 1, 0-2.5 s: medium at shoulder height, past the car's side mirror soft near the lens, camera still. The officer alone in frame at the driver's window with a small notepad, red and blue light pulsing across his face. The officer says, evenly: \"Did you scream?\"",
     "Shot 2, 2.5-7.5 s: close-up through the open driver's window, camera still. Paige alone in frame, her face turned three-quarter toward us, eyes on the steering wheel, her fist tight around her keys. Paige says, quiet and unsteady: \"I tried. Nothing came out. It was like my throat was glued shut.\"",
     "Shot 3, 7.5-10 s: low wide from the car's rear corner, past the broken eggs on the asphalt near the lens, camera still. Dana runs in from the left in her slippers to the driver's door; the officer steps back; the door swings open. Three people in frame.",
     "Shot 4, 10-13 s: medium close two-shot at the open door, camera still. Dana crouches and takes Paige's face in both hands, turning it side to side. Dana says, out of breath: \"Let me see you. Let me see you.\"",
     "Shot 5, 13-16.5 s: medium, camera still. The manager walks in from the right and stops beside the officer, her clipboard against her chest. The manager says to the officer, low: \"We've had complaints about those three for two weeks.\" Two people in frame: the manager and the officer.",
     "Shot 6, 16.5-22 s: medium two-shot from beside the car, both faces fully in frame, a slow push in on Dana as she stands up. Dana, on the left, turns from the car to the manager on the right. Dana says, sharp: \"Two weeks?\" The manager's eyes drop to the asphalt and she says nothing. Dana says, low, her voice shaking: \"And nobody said a word to a sixteen-year-old buying eggs?\" Hold on Dana's face for the last second."],
    f"{DRAMA}, night, red and blue police light from the left on wet asphalt, faces lit and readable, the background darker.",
    "Each line is spoken once, by the person named. An idling engine, a police radio murmur far off, slippers on wet asphalt.",
    ["officer", "paige", "dana", "manager"]),

"b8": clip(12, ["paige", "dana", "manager", "lotnight"],
    "The same night at Paige's open car door, under police lights. Dana turns from the manager back to her daughter and asks why she said nothing to the manager inside. Paige cannot look at her.",
    ["Shot 1, 0-4.5 s: medium close-up of Dana crouched at the open car door, camera still, the manager out of focus behind her on the right. Dana nods back toward the manager. Dana says, soft, not angry: \"She was right there, honey. Why didn't you say something to her?\"",
     "Shot 2, 4.5-9 s: close-up of Paige in the driver's seat, camera still, her face three-quarter toward us, her eyes on the floor of the car. Paige says, small: \"Mom, I don't know. I didn't think this stuff happened over here.\"",
     "Shot 3, 9-12 s: close-up of Dana, camera still. She closes her eyes, breathes out through her nose, and lays her hand on the back of Paige's head; red and blue light slides across her face. Hold."],
    f"{DRAMA}, night, red and blue police light, faces lit and readable, the background darker.",
    "An idling engine, a police radio murmur far off.",
    ["dana", "paige"]),

# ---------------------------------------------------------------- the detective at the kitchen table
"d1": clip(19, ["det", "dana", "paige", "table"],
    "The kitchen table, two days later, a grey afternoon. A detective sits across from Dana and has not touched the coffee she made him. Paige sits on the stairs in the hall behind them, where they cannot see her, listening. He tells Dana the van matched two other reports that week.",
    ["Shot 1, 0-7 s: wide from the stairs, past Paige's shoulder and the white banister soft near the lens, camera still. At the kitchen table the detective sits on the right with a full mug in front of him, Dana on the left with her hands around her own. The detective says, flat and quiet: \"The plate on that van matched two other reports this same week. They came from the shopping center across the street.\"",
     "Shot 2, 7-10 s: close-up of Dana across the table, the detective's shoulder soft near the lens, camera still. Dana says: \"Two other girls?\" The detective's head nods once at the edge of frame.",
     "Shot 3, 10-14 s: close-up of the detective over Dana's shoulder, camera still. Dana says, out of frame: \"Are they okay?\" He holds her eyes. The detective says: \"One of them is.\"",
     "Shot 4, 14-16 s: close-up of Dana, camera still. Dana says, barely: \"And the other one?\"",
     "Shot 5, 16-19 s: close on the detective's hands around the untouched mug, then up to his face as he looks down at them. The detective says: \"I can't talk about her.\""],
    f"{DRAMA}, soft grey window light from the left, the hall darker.",
    "A quiet house: a clock ticking, a fridge hum. Each line is spoken once, by the person named.",
    ["det", "dana"]),

"d2": clip(14, ["det", "dana", "paige", "table"],
    "The same afternoon at the kitchen table. On the stairs, Paige stops breathing for a second. The detective turns his laptop around to show Dana the parking-lot camera footage, which has no sound: Paige's hand comes down, a white flash, and every head in the lot turns at once. Paige looks away. Dana still does not understand why her daughter could not scream.",
    ["Shot 1, 0-2.5 s: close-up of Paige on the stairs through the white banister rails, camera still. She sits with her knees together, her breath held, eyes fixed toward the kitchen.",
     "Shot 2, 2.5-5 s: medium at table height, camera still. The detective turns his open laptop around on the table to face Dana.",
     "Shot 3, 5-9 s: the laptop's screen fills the frame: silent black-and-white security-camera footage from high on a lamp pole, grainy, wide-angle. A small figure in a parking lot beside a white van; her arm comes down, a white flash blooms, and every tiny figure in the lot turns toward it at once. No readable text on the screen.",
     "Shot 4, 9-11 s: close-up of Paige on the stairs, camera still. She turns her face away to the wall.",
     "Shot 5, 11-14 s: close-up of Dana lit by the laptop, camera still. Dana says, shaking her head: \"I don't get it. She's the most vocal girl on the block. Why couldn't she scream?\""],
    f"{DRAMA}, soft grey window light, the laptop's cold glow on Dana's face.",
    "A quiet house: a clock ticking. The footage is silent.",
    ["dana"]),

"d3": clip(15, ["det", "dana", "table"],
    "The same afternoon at the kitchen table. The detective explains to Dana how these men work. As he speaks we see what he describes as silent security-camera pictures; his voice carries on over them.",
    ["Shot 1, 0-5 s: medium close-up of the detective across the table, Dana's shoulder soft near the lens, camera still. The detective says, flat and quiet: \"Look. Fear freezes people, and these people know that.\"",
     f"Shot 2, 5-10 s: silent black-and-white security-camera view from the ceiling of a store aisle, grainy, wide-angle, a little barrel distortion: three men in identical gray sweatsuits stand far apart with empty hands. The detective's voice continues over it: \"Why do you think they wore the same clothes and didn't carry anything?\"",
     "Shot 3, 10-13.5 s: silent black-and-white security-camera view from a lamp pole of a parking lot at dusk: a white windowless van stopped across three bays, its side door open before anyone steps out. The detective's voice continues over it: \"Why do you think the van had no windows, and the door was open before they ever got out?\"",
     "Shot 4, 13.5-15 s: close-up of Dana, camera still. She does not answer; her thumb rubs the rim of her mug."],
    f"{DRAMA}, soft grey window light from the left; the two security-camera shots are black-and-white, grainy and silent.",
    "A quiet house: a clock ticking. The detective's voice runs unbroken across shots 1 to 3.",
    ["det"]),

"d4": clip(22, ["det", "dana", "paige", "table"],
    "The same afternoon at the kitchen table. The detective tells Dana why the alarm worked: these men need quiet and nobody watching, and Paige took that away the second forty people looked up. Paige listens from the stairs.",
    ["Shot 1, 0-9 s: medium close-up of the detective, a slow push in, Dana's shoulder soft near the lens. He leans his forearms on the table. The detective says, flat and quiet: \"They know what they're doing. And they also know how important it is no one ever sees them. They need it quiet, and they need nobody watching.\"",
     "Shot 2, 9-13.5 s: close-up of Dana listening, camera still, the detective's shoulder soft near the lens. The detective's voice continues, out of frame: \"She couldn't have fought off two grown men, and she didn't need to.\" Dana's eyes come up to his.",
     "Shot 3, 13.5-19 s: close-up of the detective, camera still. The detective says: \"The only thing that really stops them is their own decision to walk away, and she made that decision for them\"",
     "Shot 4, 19-22 s: close-up of Paige on the stairs through the white banister rails, camera still, her chin on her knees. The detective's voice finishes over her face: \"the second forty people looked up.\" Her eyes lift."],
    f"{DRAMA}, soft grey window light from the left, the hall darker.",
    "A quiet house: a clock ticking. The detective's voice runs unbroken from shot 1 to shot 4; his sentence in shots 3 and 4 is one sentence.",
    ["det"]),

"d5": clip(15, ["det", "paige", "dana", "table"],
    "The same afternoon at the kitchen table. The detective says the thing Paige most needs to hear, not knowing she is on the stairs: freezing is not weakness. Paige pulls her knees up to her chest.",
    ["Shot 1, 0-4.5 s: medium close-up of the detective, camera still, Dana's shoulder soft near the lens. The detective says, flat and quiet: \"Noise and attention are predator repellent. They know it better than anybody.\"",
     "Shot 2, 4.5-10 s: close-up of Paige on the stairs through the white banister rails, camera still. She pulls her knees up to her chest and wraps her arms around them. The detective's voice carries from the kitchen: \"And freezing isn't weakness. It happens to almost every girl, the tough ones too.\"",
     "Shot 3, 10-15 s: close-up of the detective, a slow push in to his eyes; he looks down at the mug, then back up at Dana. The detective says, quieter: \"The ones I never get back are the ones who froze and nobody heard them.\" Hold."],
    f"{DRAMA}, soft grey window light from the left, the hall darker.",
    "A quiet house: a clock ticking. Only the detective speaks.",
    ["det"]),

"d6": clip(20, ["det", "dana", "table"],
    "The same afternoon at the kitchen table. The detective asks Dana where she bought the alarm. She does not remember, opens her own laptop, scrolls back to an order from August, and finds it.",
    ["Shot 1, 0-8 s: medium close-up of the detective, camera still, Dana's shoulder soft near the lens. The detective says, flat and quiet: \"That alarm saved her life. Drawing attention is the most powerful thing she has. It's the one thing they can't take off her.\" A beat. \"Do you know where you got it?\"",
     "Shot 2, 8-12 s: medium close-up of Dana, camera still. She blinks, reaches for her laptop and opens it. Dana says: \"I, um, I don't know. Let me see.\"",
     "Shot 3, 12-14 s: close over Dana's shoulder, camera still: her fingers scroll a laptop trackpad; the screen is a soft blur of a list, no readable words.",
     "Shot 4, 14-17 s: close-up of Dana lit by the screen, camera still. She finds it. Dana says: \"Oh, that's right, from a small company called Palace Guard.\"",
     "Shot 5, 17-20 s: close-up of the detective, camera still. He nods once. The detective says: \"Good. You made the right choice.\""],
    f"{DRAMA}, soft grey window light from the left, the laptop's glow on Dana's face.",
    "A quiet house: a clock ticking, laptop keys. Each line is spoken once, by the person named.",
    ["det", "dana"]),

"d7": clip(16, ["det", "dana", "table"],
    "The same afternoon at the kitchen table. The detective tells Dana about the cheap alarms he has been handed in evidence bags, and that his own daughters carry this one. As he speaks we see one of those evidence bags.",
    ["Shot 1, 0-4 s: medium close-up of the detective, camera still, Dana's shoulder soft near the lens. The detective says, flat and quiet: \"I've had the cheap ones handed to me in evidence bags.\"",
     "Shot 2, 4-9 s: close insert, camera still: a clear plastic evidence bag on a grey steel desk under one hard lamp, a cheap black keychain alarm inside it, its casing cracked open, a blank white label on the bag. The detective's voice continues over it: \"Dead battery, or cracked the first time they hit the ground.\"",
     "Shot 3, 9-13 s: close-up of the detective, camera still. The detective says: \"Some girls carried them for years, and they didn't work the one night it mattered.\"",
     "Shot 4, 13-16 s: close-up of the detective, a small softening, the first almost-smile; Dana's shoulder soft near the lens. The detective says: \"My own daughters carry a Palace Guard one around as well.\""],
    f"{DRAMA}, soft grey window light from the left; the evidence-bag shot is cold and hard-lit.",
    "A quiet house: a clock ticking. The detective's voice runs unbroken across shots 1 to 3.",
    ["det"]),

"d8": clip(23, ["dana", "paige", "det", "table"],
    "The same afternoon at the kitchen table. Dana admits she almost did not buy the alarm. From the stairs Paige speaks for the first time, and they both turn: she has been there the whole time.",
    ["Shot 1, 0-10 s: medium close-up of Dana, a slow push in, the detective's shoulder soft near the lens. Her eyes are on her mug. Dana says: \"I almost didn't buy it. I picked that one because it's a real 130 decibels, it's got the strobe light, and it was the only one she'd agree to carry because she liked the colors.\"",
     "Shot 2, 10-13 s: close-up of Paige on the stairs through the white banister rails, camera still. Paige says, quiet, almost a smile: \"And because it doesn't go off in class.\"",
     "Shot 3, 13-15 s: wide from the stairs, past Paige's shoulder soft near the lens, camera still. At the table Dana and the detective both turn in their chairs to look at her. Three people in frame.",
     "Shot 4, 15-20 s: close-up of the detective turned toward the stairs, camera still. The detective says, gently: \"That's probably the only reason it was on her keys that night instead of in a drawer.\"",
     "Shot 5, 20-23 s: close-up of Dana looking at her daughter, her eyes wet, camera still. Dana says: \"And it turns out it saved her life.\" Hold."],
    f"{DRAMA}, soft grey window light from the left, the hall darker.",
    "A quiet house: a clock ticking. Each line is spoken once, by the person named.",
    ["dana", "paige", "det"]),

# ---------------------------------------------------------------- Paige's closing words, over pictures
"c1": clip(12, ["alarm", "kitchen"],
    "Close pictures around the family's house at night while Paige speaks as a voice-over. Nobody is seen speaking. The same white alarm hangs on three things.",
    ["Shot 1, 0-4 s: close insert, camera still: Paige's keys on the butcher-block kitchen counter under the pendant lamp, the white alarm on the ring beside a car key. Paige's voice-over, plain and steady: \"We live in a safe neighborhood. We leave the garage open.\"",
     "Shot 2, 4-8 s: close insert, camera still: a tan leather purse hanging on a chair back, the same white alarm clipped to its strap. The voice-over continues: \"My mom never believed this kind of thing actually happens,\"",
     "Shot 3, 8-12 s: close insert, a slow push in: a child's purple backpack by the front door, a third white alarm on its zipper. The voice-over continues: \"let alone to me, in a Target, with a manager ten feet away.\""],
    f"{DRAMA}, warm lamp light, deep shadows, each object off-centre.",
    "Paige's voice-over runs unbroken across the three shots as one thought. A quiet house under it.",
    ["paige"]),

"c2": clip(13, ["paige", "manager", "lot", "checkout"],
    "Two memories of that night while Paige speaks as a voice-over to the mothers watching. Nobody is seen speaking.",
    ["Shot 1, 0-6.5 s: the parking lot at dusk: close-up of Paige frozen under the flickering lamp, her mouth open, no sound, a slow push in to her eyes. Paige's voice-over, plain and steady: \"So maybe your daughter's tough like me. I broke my brother's nose, and my body still wouldn't move.\"",
     "Shot 2, 6.5-13 s: the self-checkout: wide from the end of the kiosk row, the nearest kiosk soft at the left edge, camera still. A shopper bags groceries at another kiosk. Paige walks past the manager, who reads her clipboard; Paige's eyes go to her and away, and she keeps walking out of frame. The voice-over continues: \"Maybe she'd ask somebody for help. I walked right past a manager because I didn't want to be dramatic.\""],
    f"{DRAMA}; the lot at dusk under a deep blue sky, the store under cool fluorescent light.",
    "Paige's voice-over only; under it the lot's quiet, then the store's hum.",
    ["paige"]),

"c3": clip(16, ["dana", "kitchen", "lot"],
    "Pictures of the people who worry while Paige speaks as a voice-over. Nobody is seen speaking.",
    ["Shot 1, 0-4 s: close insert over Dana's hand in the kitchen, camera still: her phone shows a map with one blue dot on a parking lot, no readable words. Paige's voice-over, plain and steady: \"Maybe you track her phone. So does my mom.\"",
     "Shot 2, 4-8.5 s: the parking lot at dusk, wide from high on a lamp pole, camera still: a small figure beside a silver car, a white van stopped three bays away, two small figures walking toward her. The voice-over continues: \"The dot showed her exactly where I was while two men walked toward me.\"",
     "Shot 3, 8.5-13 s: a different house: close-up of a grey-haired woman in her 70s in a cardigan at a window at night, a phone held in both hands, looking out at an empty street. The voice-over continues: \"Maybe you're her grandma, and you worry about her more than anybody knows.\"",
     "Shot 4, 13-16 s: the parking lot at dusk, empty, wide and low, camera still, one lamp flickering over the silver car. The voice-over continues: \"You can't be in that parking lot with her. Nobody can.\""],
    f"{DRAMA}; warm lamp light indoors, a deep blue dusk outside.",
    "Paige's voice-over runs unbroken across the four shots. Quiet under it.",
    ["paige"]),

"c4": clip(18, ["paige", "alarm", "kitchen"],
    "The alarm itself, close, while Paige speaks as a voice-over. Nobody is seen speaking.",
    ["Shot 1, 0-6 s: close-up of Paige at the kitchen counter under the pendant lamp, camera still, turning her keys over in her hand, looking at the white alarm on them. Paige's voice-over, plain and steady: \"The only difference between me and the girl the detective couldn't talk about was what was on my keys.\"",
     "Shot 2, 6-11.5 s: extreme close-up, camera still: the white alarm on a key ring beside a car key, the same length as the key. One hand holds the white body; two fingers of the other hook through the round ring at its top and pull it straight up and out of the body. The ring comes away with the keys on it, and the round lens on the body fires a hard white strobe. The voice-over continues: \"It clips on your keys, it's lighter than a car key, and it's as loud as an ambulance.\"",
     "Shot 3, 11.5-18 s: close insert, a slow push in: the white alarm hanging from the zip of a school backpack on a hook in a school corridor, lockers out of focus behind. The voice-over continues: \"It's not a weapon, so a school can't take it and nobody can use it on her.\""],
    f"{DRAMA}, warm lamp light in the kitchen, cool daylight in the corridor; the alarm always sharp, at its real size.",
    "Paige's voice-over runs unbroken; one short burst of the siren under the strobe in shot 2, low.",
    ["paige"]),

"c5": clip(20, ["dana", "alarm", "table"],
    "Dana at the kitchen table at night with the alarms she ordered, while Paige speaks as a voice-over. Nobody is seen speaking.",
    ["Shot 1, 0-5.5 s: high angle over the oak kitchen table, camera still: five of the same alarm laid in a row, white, black, royal blue, pale pink and lavender, beside a small open cardboard box. Paige's voice-over, plain and steady: \"My mom bought three and got two free, so it came out to less than twenty dollars each.\"",
     "Shot 2, 5.5-10 s: close-up of Dana at the table, reading glasses on, lit by her laptop, reading closely, her lips closed. The voice-over continues: \"There's a thirty-day guarantee too. She checked, because she reads everything now.\"",
     "Shot 3, 10-15.5 s: close insert, camera still: a man's weathered hands at a workbench under a lamp setting one white alarm into a small cardboard box, a short row of boxes beside it. The voice-over continues: \"A detective makes them in small batches, and we waited about a week for ours because they were sold out.\"",
     "Shot 4, 15.5-20 s: close on Dana's hand, camera still: she clips a white alarm onto a set of keys and sets them by the front door. The voice-over continues: \"So if the link still works, they've still got some.\""],
    f"{DRAMA}, warm lamp light and the laptop's glow, the kitchen dark behind; the alarms sharp, at their real size.",
    "Paige's voice-over says exactly the quoted words, word for word, in American English, unbroken across the four shots. A quiet house under it.",
    ["paige"]),

"c6": clip(17, ["det", "dana", "paige", "alarm", "table"],
    "The last pictures, while Paige speaks as a voice-over, ending on Paige herself looking at us. Nobody is seen speaking.",
    ["Shot 1, 0-6 s: a different kitchen table, close over a mother's and father's clasped hands, the detective out of focus across from them, his eyes down, camera still. Paige's voice-over, plain and steady: \"That detective has sat with parents whose girls froze just like I did, and nobody heard them.\"",
     "Shot 2, 6-8.5 s: close-up of Dana in her doorway at night, camera still, watching something out of frame, one hand flat on her chest. The voice-over continues: \"And my mom almost didn't buy it.\"",
     "Shot 3, 8.5-13 s: medium, camera still: Dana holds Paige tight in the front hall, Paige's keys with the white alarm hanging from her hand at Dana's back. The voice-over continues: \"Share this with every mother you know so their daughter doesn't get abducted or assaulted.\"",
     "Shot 4, 13-17 s: close-up of Paige at the front door, a slow push in. She lifts her keys so the white alarm hangs beside her face and looks straight into the lens, her lips closed. The voice-over finishes: \"The link's right there. Don't wait until it's too late.\" Hold on her eyes."],
    f"{DRAMA}, warm lamp light, the background dark; the alarm sharp, at its real size.",
    "Paige's voice-over runs unbroken across the four shots. A quiet house under it.",
    ["paige"]),
}


# ---------------------------------------------------------------- round 2 (Reed's notes, 13 Nov)
# "the men in gray just kinda stand and don't look menacing, or they aren't looking at the main
# character ... which was the whole point"; "one more cut from her face ... to the men menacingly
# approaching ... so it feels like an impending doom"; the pull "doesn't feel dramatic, like it is
# going to save her life"; the siren "is more of a very high pitched, loud whistle"; "the strobe is
# more intense"; "the men don't look shocked enough or run off with enough emotion"; "the wrong car
# drives off"; in her car "she should still be ringing with the alarm"; "the parking lot is overly
# empty"; cut the brother's-nose line. Each clip below REPLACES its first version.
THRILL = ("photoreal thriller footage, long lens, shallow focus, the acting real: people react the way "
          "people really do, fear and shock plain in the face and body, nothing staged")
WHISTLE = ("a piercing, very high-pitched electronic whistle, painfully loud and unbroken, like a "
           "referee's whistle held without a breath")
STROBE = "a blinding, rapid white strobe that lights faces, cars and wet asphalt in hard flashes"
JOB["lot"] = "{lot} is the parking lot and Paige's silver car among other parked cars: use it for the place, the car, the light and the colour, not for framing."

CLIPS["b1"] = clip(26, ["paige", "mig", "store"],
    "A Tuesday evening in a big-box store. Ordinary shoppers push trolleys and carry baskets, going about their evening. Paige shops with a red basket on her forearm, a gallon of milk in it. Three men in identical gray sweatsuits and work boots, with no trolleys and empty hands, are watching her. Each time she looks up, one of them is staring straight at her and looks away a beat too late. They never come closer; they keep her in sight. Her thoughts are heard as a voice-over; her lips stay closed all through.",
    ["Shot 1, 0-3 s: medium close-up at eye height, past the soft edge of the egg cooler near the lens, camera still. Paige alone in frame, on the left, side-on to the cooler, lifting a carton of eggs; she feels eyes on her, her hand stops and she looks up toward the far end of the aisle.",
     "Shot 2, 3-6.5 s: long-lens shot down the aisle between two shelf ends, camera still. The man in gray alone in frame, small at the far end and off to the right, hands in his pockets, no trolley, head a little lowered, staring straight at her, straight into the lens, without blinking. He holds it a beat too long, then his eyes slide away to a shelf. Paige's thought is heard, flat and dry: \"Weird. But whatever.\"",
     f"Shot 3, 6.5-10 s: medium shot tracking beside Paige as she walks the main aisle, the basket on her forearm; a woman with a full trolley passes behind her. Paige glances into a side aisle: {GREY2} stands square to her, not to the shelves, arms loose, eyes locked on her. Caught, he turns his head slowly to a shelf.",
     f"Shot 4, 10-14 s: wide from a corner along the freezer wall, past a glowing freezer door near the lens, camera still. {GREY3} stands with his back to the freezer doors, facing the aisle, his head turning to follow Paige as she crosses the foreground; beside him a father and a small boy choose ice cream and notice nothing. Her thought is heard, easy and quick: \"Construction guys, probably. I bet they're just on a break.\"",
     "Shot 5, 14-17.5 s: low wide from the corner of the cereal aisle, past a shelf end of cereal boxes soft near the lens, camera still. Paige walks away from us down the aisle, small, on the left; at the far cross-aisle a man in a gray sweatsuit crosses slowly from left to right, his face turned toward her the whole way across.",
     "Shot 6, 17.5-20 s: high angle over her shoulder into the basket, camera still. Paige has stopped. A gallon of milk and a carton of eggs in the red basket; her fingers tighten on the handle.",
     "Shot 7, 20-22.5 s: medium-wide over Paige's right shoulder, her shoulder soft near the lens, camera still. At the far cross-aisle the three men in gray stand spread apart, all three facing her, hands empty, heads a little lowered, all three looking straight at her. A shopper with a trolley walks between them and notices nothing. None of the three moves.",
     "Shot 8, 22.5-26 s: close-up of Paige from the front-left, a slow push in to her eyes, fixed on the far end; a tight swallow, her breath shallow. Her thought is heard, quiet and slow: \"Wait. Nobody's buying anything.\""],
    f"{THRILL}. The three men are still and unblinking; her unease grows. Cool fluorescent tubes overhead, the aisle ends darker.",
    "Fluorescent hum, freezer compressors, trolley wheels, sneakers on concrete, a distant checkout beep. The voice-over is Paige's inner voice; nobody speaks aloud.",
    ["paige"])

CLIPS["b4"] = clip(24, ["paige", "mig", "alarm", "lot", "van"],
    "The back half of a half-full parking lot at dusk, under a lamp that is half out. Paige walks to her silver car with her keys in her right hand and a grocery bag in her left. A white windowless van rolls up and stops three bays away with its side door already open. Two men get out and walk straight at her, eyes fixed on her, never hurrying and never slowing. She backs against her car and freezes: her thoughts are heard as a voice-over while her mouth makes no sound. We keep cutting between her face and the men getting closer.",
    ["Shot 1, 0-3 s: low wide past a parked car's bumper soft near the lens, camera still. Paige walks left to right between parked cars toward her silver car under the flickering lamp, keys in her right hand, the bag in her left; far behind her a couple load shopping into a car boot.",
     "Shot 2, 3-6 s: over Paige's right shoulder, three steps from her car door, camera still. The white van rolls in and stops three bays away, its side door already open, black inside. Her thought is heard, quiet: \"Why is the door already open?\"",
     f"Shot 3, 6-9.5 s: medium from a low angle, camera still. The man in gray and {GREY2} step out of the van and walk straight toward the camera, shoulders square, eyes fixed on her, not hurrying. The man in gray says, a friendly voice and dead eyes: \"Hey. Hey, you dropped something.\"",
     "Shot 4, 9.5-12.5 s: close-up of Paige, camera still. Her eyes drop to her hands and come back up; she takes one step back and her shoulders hit her car door. Her thought is heard: \"I didn't drop anything.\"",
     "Shot 5, 12.5-14.5 s: from her eye height, camera still. The two men are closer and larger in the frame, still walking straight at us, eyes on her; the man in gray's right hand comes out of his pocket. They do not slow.",
     "Shot 6, 14.5-18.5 s: tighter close-up of Paige, a slow push in to her eyes. Her mouth opens, her throat works, and no sound comes out; her breath stops. Her thought is heard, faster: \"Scream. Just scream. Why can't I scream?\"",
     "Shot 7, 18.5-20.5 s: low angle at asphalt level, camera still. Her white sneakers pressed back against her car's tyre, sharp near the lens; beyond them two pairs of tan work boots, four steps away, still coming.",
     "Shot 8, 20.5-24 s: extreme close-up of her hands at her chest, camera still. Her left hand closes around the white body of the alarm among her keys; two fingers of her right hand hook into the round ring at its top. Her thought is heard, urgent: \"The thing on my keys. Pull it.\" End on her fingers tightening in the ring."],
    f"{THRILL}. The men are calm and certain. Dusk, a deep blue sky, one flickering lamp overhead, the van's black doorway.",
    "A quiet lot: an engine idling, slow boots on wet asphalt getting louder, the lamp's buzz, her breathing. The voice-over is Paige's inner voice; only the man in gray speaks aloud.",
    ["paige", "mig"])

CLIPS["b5"] = clip(24, ["paige", "mig", "kid", "stroller", "alarm", "lot", "van"],
    "The same moment in the half-full parking lot at dusk, a dozen ordinary shoppers scattered across it. Paige is backed against her silver car with two men in gray almost on her. She drops her groceries, thrusts her alarm out at them and rips the ring out of its top. A piercing whistle screams across the lot and a blinding strobe fires in the men's faces. Every head in the lot turns. The two men panic and run for the white van, which speeds away with its side door still open; Paige's silver car never moves. The cart kid chases the van with his phone up. Paige locks herself in her car with the alarm still screaming and flashing in her hands.",
    ["Shot 1, 0-2.5 s: medium on Paige backed against her car, the two men's shoulders dark and soft near the lens, closing in. She lets go of the grocery bag to free her left hand; it drops out of the bottom of the frame and the eggs burst on the asphalt.",
     "Shot 2, 2.5-7 s: close from a low angle, a slow push in. Paige thrusts the alarm out at arm's length toward the men: her left hand grips its white body, two fingers of her right hand are hooked in the round ring at its top. Her jaw sets. She rips the ring straight up and out of the body in one hard pull, her right hand flying up with the ring and her keys. The instant it comes out, the round lens on the body explodes into " + STROBE + " and the whistle starts.",
     f"Shot 3, 7-10 s: medium on the two men from beside Paige, camera still. The strobe hits their faces: both flinch hard; the man in gray throws a forearm across his eyes; {GREY2} staggers back a step, mouth open. They look around wildly at the lot.",
     "Shot 4, 10-13 s: wide across the lot from a low corner, a cart corral soft near the lens, camera still, white flashes sweeping the parked cars. Every head snaps toward the sound at once: a man at his open car boot, a couple with a full trolley, two teenagers by a pickup, the cart kid behind a line of carts, and the woman with the stroller, who stops so fast the stroller rolls a foot ahead of her.",
     "Shot 5, 13-17 s: wide, handheld. The two men turn and run for the white van in a panic; one slips on the wet asphalt and scrambles up; they dive in through the open side door. The white van lurches forward and speeds toward the exit, tyres squealing, its side door still open. Paige's silver car stays parked where it is.",
     "Shot 6, 17-20 s: handheld, tracking beside the cart kid as he lets go of his carts and sprints after the white van with his phone held up. The cart kid yells: \"I got the plate! I got it!\"",
     "Shot 7, 20-24 s: through the windscreen of Paige's parked silver car, camera still. Paige drops into the driver's seat and slams the door; the locks clunk. She clutches the white alarm body against her chest with both hands, its lens still firing white flashes across her face and the windscreen, the whistle still screaming inside the car. She gasps for air. Paige alone in frame. Hold."],
    f"{THRILL}. Her pull is fierce and deliberate, the thing that saves her. Dusk, " + STROBE + ".",
    "Before the pull: slow boots and her breathing. From the pull in shot 2 to the last frame the alarm never stops: " + WHISTLE + ", a little muffled inside the car in the last shot. Under it: shouts across the lot, running boots, squealing tyres, car locks.",
    ["kid"])

CLIPS["h1"] = clip(15, ["stroller", "kid", "paige", "alarm", "lot", "van"],
    "Dusk in a half-full big-box store parking lot, seconds after an attempted abduction. A personal alarm is screaming a piercing whistle and its strobe flashes across the lot; shoppers stand frozen by their cars, staring. A white windowless van speeds away with its side door still open. A woman with a stroller runs with her phone to her ear, a cart attendant chases the van, and Paige stands frozen over a carton of broken eggs with the alarm still going off in her hand.",
    ["Shot 1, 0-5 s: low wide from between two parked cars, a bumper soft near the lens, camera still. The white van speeds away toward the exit on the right, its side door open, white flashes sweeping across it; shoppers by their cars stare after it. The woman with the stroller runs in from the left, pushing the stroller one-handed, phone at her ear. She shouts into the phone: \"Two men just tried to abduct a girl in the Target parking lot! They're in a white van, it's leaving!\"",
     "Shot 2, 5-8 s: handheld, tracking beside the cart kid at shoulder height as he sprints after the van with his phone held up, filming it. The cart kid alone in frame. He yells: \"I got the plate! I got it!\"",
     "Shot 3, 8-11 s: close on Paige's hands at her sides. Her left hand holds the white body of the alarm, its round lens firing white flashes; her right hand holds the pulled-out ring with her keys hanging from it. A crushed egg carton and broken eggs lie on the asphalt by her white sneakers. The camera tilts up to her face: eyes wide, lips parted, chest heaving, not moving.",
     "Shot 4, 11-15 s: medium two-shot, camera still. Paige on the right, frozen, the alarm body still flashing in her left hand. The woman with the stroller reaches her on the left and grips her arm, phone still at her ear. She says into the phone, catching her breath: \"She's okay. She's standing right here. They almost got her.\" Hold on Paige's face for the last second."],
    f"{THRILL}. Dusk, a deep blue sky, lot lamps just on, " + STROBE + ".",
    "Through the whole clip, under the voices, the alarm: " + WHISTLE + ". An engine speeding away, running footsteps, a shout far off.",
    ["stroller", "kid"])

CLIPS["d3"] = clip(15, ["det", "dana", "table"],
    "The same afternoon at the kitchen table. The detective explains to Dana how these men work. As he speaks we see what he describes as silent security-camera pictures; his voice carries on over them.",
    ["Shot 1, 0-5 s: medium close-up of the detective across the table, Dana's shoulder soft near the lens, camera still. The detective says, flat and quiet: \"Look. Fear freezes people, and these people know that.\"",
     "Shot 2, 5-10 s: silent black-and-white security-camera view from the ceiling of a store aisle, grainy, wide-angle, a little barrel distortion. Near the bottom of the frame a girl with a ponytail and a shopping basket stands at a shelf. Spaced along the aisle beyond her, three men in identical gray sweatsuits stand with empty hands, all three turned toward her, all three watching her; two shoppers with trolleys pass between them. The detective's voice continues over it: \"Why do you think they wore the same clothes and didn't carry anything?\"",
     "Shot 3, 10-13.5 s: silent black-and-white security-camera view from a lamp pole of a half-full parking lot at dusk: a white windowless van stops three bays from a girl walking to her car, its side door already open before anyone steps out. The detective's voice continues over it: \"Why do you think the van had no windows, and the door was open before they ever got out?\"",
     "Shot 4, 13.5-15 s: close-up of Dana, camera still. She does not answer; her thumb rubs the rim of her mug."],
    f"{DRAMA}, soft grey window light from the left; the two security-camera shots are black-and-white, grainy and silent.",
    "A quiet house: a clock ticking. The detective's voice runs unbroken across shots 1 to 3.",
    ["det"])

CLIPS["c2"] = clip(11, ["paige", "manager", "lot", "checkout"],
    "Two memories of that night while Paige speaks as a voice-over to the mothers watching. Nobody is seen speaking.",
    ["Shot 1, 0-4.5 s: the parking lot at dusk: close-up of Paige backed against her car under the flickering lamp, her mouth open, no sound, her whole body rigid, a slow push in to her eyes. Paige's voice-over, plain and steady: \"So maybe your daughter's tough like me.\"",
     "Shot 2, 4.5-11 s: the self-checkout: wide from the end of the kiosk row, the nearest kiosk soft at the left edge, camera still. A shopper bags groceries at another kiosk. Paige walks past the manager, who reads her clipboard; Paige's eyes go to her and away, and she keeps walking out of frame. The voice-over continues: \"Maybe she'd ask somebody for help. I walked right past a manager because I didn't want to be dramatic.\""],
    f"{DRAMA}; the lot at dusk under a deep blue sky, the store under cool fluorescent light.",
    "Paige's voice-over says exactly the quoted words, word for word; under it the lot's quiet, then the store's hum.",
    ["paige"])


# ---------------------------------------------------------------- round 3 (Reed, 13 Nov)
# "The hooks i think need more work, all of them honestly, in a similar manner." "The pulling of
# the alarm didn't happen fast enough ... She kinda slowly pulls it and thinks, versus yanking it
# when men are running at her ... She also 'pulls it' twice." (The alarm's own sound is laid in
# from Reed's recording in the cut: `cut.py`.) Each clip below REPLACES its earlier version.
CLIPS["b4"]["shots"][-1] = ("Shot 8, 20.5-24 s: extreme close-up of her right hand at her side, camera still. "
    "Among her keys her fist closes hard around the white alarm, knuckles white. Her thought is heard, urgent: "
    "\"The thing on my keys. Pull it.\" End on her fist. Nothing is pulled in this clip.")

CLIPS["b5"] = clip(22, ["paige", "mig", "kid", "stroller", "alarm", "lot", "van"],
    "The same second in the half-full parking lot at dusk, a dozen ordinary shoppers scattered across it. Paige is backed against her silver car. The two men in gray break into a run at her and the man in gray reaches for her arm. In one desperate yank she rips the ring out of the top of her alarm, once: a whistle screams across the lot and a blinding strobe fires in the men's faces. Every head in the lot turns. The men panic and run for the white van, which speeds away with its side door still open; Paige's silver car never moves. The cart kid chases the van with his phone up. Paige locks herself in her car with the alarm still screaming and flashing in her hands.",
    [f"Shot 1, 0-2 s: from Paige's eye height, handheld. The man in gray and {GREY2} break from a walk into a run straight at the lens, four steps away; the man in gray's hand reaches out for her arm.",
     "Shot 2, 2-4 s: close on Paige from a low angle, camera still. No hesitation: her left hand grips the white body of the alarm, her right hand is already on the round ring at its top, and in the first half second she yanks the ring out of the body in one violent pull, her right arm flying up and back with the ring and her keys, the grocery bag falling from her elbow and the eggs bursting at her feet. She pulls once. After the yank the top of the white body is flat and empty, the ring gone from it, the ring and her keys in her raised right fist. For the rest of the shot she holds the body out at the men, its round lens firing " + STROBE + ".",
     f"Shot 3, 4-7 s: medium on the two men from beside Paige, camera still. The strobe hits their faces mid-stride: both stop dead and flinch hard; the man in gray throws a forearm across his eyes; {GREY2} stumbles back, mouth open. They look around wildly at the lot.",
     "Shot 4, 7-10 s: wide across the lot from a low corner, a cart corral soft near the lens, camera still, white flashes sweeping the parked cars. Every head snaps toward the sound at once: a man at his open car boot, a couple with a full trolley, two teenagers by a pickup, the cart kid behind a line of carts, and the woman with the stroller, who stops so fast the stroller rolls a foot ahead of her.",
     "Shot 5, 10-14 s: wide, handheld. The two men turn and run for the white van in a panic; one slips on the wet asphalt and scrambles up; they dive in through the open side door. The white van lurches forward and speeds toward the exit, tyres squealing, its side door still open. Paige's silver car stays parked where it is.",
     "Shot 6, 14-17 s: handheld, tracking beside the cart kid as he lets go of his carts and sprints after the white van with his phone held up. The cart kid yells: \"I got the plate! I got it!\"",
     "Shot 7, 17-22 s: through the windscreen of Paige's parked silver car, camera still. Paige drops into the driver's seat and slams the door; the locks clunk. She clutches the white alarm body against her chest with both hands, its lens still firing white flashes across her face and the windscreen, the whistle still screaming inside the car. She gasps for air, shaking. Paige alone in frame. Hold."],
    f"{THRILL}. Dusk, " + STROBE + ".",
    "Before the pull: boots running on wet asphalt and her breath. From the pull in shot 2 to the last frame the alarm never stops: " + WHISTLE + ", a little muffled inside the car in the last shot. Under it: shouts across the lot, running boots, squealing tyres, car locks.",
    ["kid"])

CLIPS["h1"] = clip(16, ["stroller", "kid", "paige", "mig", "alarm", "lot", "van"],
    "Dusk in a half-full big-box store parking lot, in the seconds after an attempted abduction. Paige's alarm is screaming a piercing whistle and its strobe flashes across the lot. The man in gray dives into a white windowless van as it speeds away with its side door open; shoppers by their cars shout and point. A terrified woman with a stroller runs to Paige with her phone to her ear, a cart attendant chases the van, and Paige stands shaking over a carton of broken eggs with the alarm still going off in her hand.",
    ["Shot 1, 0-2 s: extreme close-up of Paige's face, camera still. Hard white flashes hit it from below, again and again; her eyes are wide and wet, her mouth open, her breath coming in jerks.",
     "Shot 2, 2-6.5 s: wide from between two parked cars, a bumper soft near the lens, handheld. Beyond Paige the man in gray dives through the open side door of the white van as it lurches away toward the exit, tyres squealing; shoppers by their cars shout and point after it. The woman with the stroller runs in from the left, dragging the stroller one-handed, phone at her ear, terrified. She shouts into the phone: \"Two men just tried to abduct a girl in the Target parking lot! They're in a white van, it's leaving!\"",
     "Shot 3, 6.5-9 s: handheld, tracking beside the cart kid at shoulder height as he sprints flat out after the van with his phone held up, filming it, nearly losing his footing. The cart kid alone in frame. He yells: \"I got the plate! I got it!\"",
     "Shot 4, 9-12 s: close on Paige's hands at her sides. Her left hand holds the white body of the alarm, its round lens firing white flashes; her right hand holds the pulled-out ring, shaking so hard her keys rattle on it. A crushed egg carton and broken eggs lie on the asphalt by her white sneakers. The camera tilts up to her face: chest heaving, tears on her cheeks, eyes fixed on where the van went.",
     "Shot 5, 12-16 s: medium two-shot, camera still. The woman with the stroller reaches Paige and pulls her in with one arm around her shoulders, phone still at her ear; Paige's knees give a little and she grabs the woman's vest. The woman says into the phone, catching her breath: \"She's okay. She's standing right here. They almost got her.\" Hold on Paige's face for the last second."],
    f"{THRILL}. Dusk, a deep blue sky, lot lamps just on, " + STROBE + ".",
    "Through the whole clip, under the voices, the alarm: " + WHISTLE + ". Squealing tyres, running footsteps, shoppers shouting.",
    ["stroller", "kid"])

CLIPS["h2"] = clip(15, ["dana", "kitchen"],
    "Just after sunset in a family kitchen. The oven timer beeps. Dana's phone shows her daughter's dot in the store parking lot, then rings: Paige. She answers smiling, and a police officer tells her three men just tried to abduct her daughter. Her legs give way and she ends on the kitchen floor.",
    ["Shot 1, 0-2.5 s: close over Dana's shoulder at the counter, camera still. Her phone on the butcher-block shows a map with one blue dot on a large parking lot; it buzzes with an incoming call, the name \"Paige\" on the screen. She smiles and picks it up. An oven timer beeps.",
     "Shot 2, 2.5-4.5 s: medium close-up of Dana, camera still, a chair back soft near the lens. Phone at her ear, smiling, a dish towel over her shoulder. Dana says, easy: \"Hey, did you get the eggs?\"",
     "Shot 3, 4.5-10.5 s: close-up of Dana, a slow push in to her eyes. A man's voice comes through the phone, thin and filtered, steady: \"Ma'am, this is the police. Your daughter's safe, she's with me. Three men just tried to abduct her in the Target parking lot.\" Her lips stay closed while he speaks. At his first words her smile dies; by the end her free hand has flown to her mouth, her eyes have filled and she has stopped breathing.",
     "Shot 4, 10.5-12.5 s: medium from the side, camera still. She reaches back for the counter without looking and her hand sweeps the mixing bowl off it; it shatters on the floor. She does not look at it. Her knees give.",
     "Shot 5, 12.5-15 s: low angle from the floor, pieces of the bowl soft near the lens, camera still. Dana is down against the cabinet, the phone crushed to her ear, her other hand over her mouth, shaking. Dana says, a broken whisper: \"Oh my god, my baby.\" The oven timer is still beeping."],
    f"{THRILL}. Warm lamp light on her face, the deep blue window behind, the background darker.",
    "The officer is heard only through the phone, thin and filtered: a man in his 40s, low and even. A phone buzzing on wood, an oven timer beeping to the end, a bowl shattering, her breath.",
    ["dana"])

CLIPS["h3"] = clip(17, ["paige", "mig", "lot", "van"],
    "Dusk at the front of a big-box store, shoppers coming and going. Paige walks out to the half-full parking lot with a grocery bag and her keys. Behind the glass doors a man in gray never takes his eyes off her and phones it in. Out in the lot a white windowless van turns its lights on and rolls up near her silver car with its side door already open; two men get out and come straight at her. She backs into her car, tries to scream, and nothing comes out.",
    ["Shot 1, 0-2.5 s: extreme close-up of the man in gray's eyes behind glass, lot lamps reflected across it, camera still: cold, fixed, following something. The focus pulls through the glass to Paige, small, walking away into the lot with a plastic grocery bag in her left hand and her keys in her right.",
     "Shot 2, 2.5-8 s: medium close-up of the man in gray behind the glass, camera still. Phone at his ear, his eyes never leaving her, his lips barely moving. A shopper pushes a trolley past behind him and notices nothing. He says into the phone, low: \"Yo, boss, I've got our next target. The tall one in the volleyball sweatshirt. She's parked in the back half of the lot.\"",
     "Shot 3, 8-10 s: low wide down a row of parked cars, camera still. At the far end the white van's headlights snap on and it rolls forward.",
     f"Shot 4, 10-13 s: over Paige's right shoulder at her car door, her keys out, camera still. The white van stops three bays away, its side door already open, black inside. Two men step out and come straight at her, fast, eyes on her: {GREY2}, and {GREY3}.",
     "Shot 5, 13-15 s: close-up of Paige, camera still. She backs into her car door; the grocery bag slips from her hand; her mouth opens wide to scream and no sound comes out.",
     "Shot 6, 15-17 s: from her eye height, handheld. The two men are almost on her, filling the frame, one hand reaching toward the lens. End on the hand."],
    f"{THRILL}. Dusk, a deep blue sky, lot lamps just on, the store's glow behind.",
    "Automatic doors and trolley wheels, then the quiet lot: an engine idling, fast boots on wet asphalt, a bag hitting the ground, her breath; no scream.",
    ["mig"])

ORDER = {"hooks": ["h1", "h2", "h3"],
         "body": ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "d1", "d2", "d3", "d4", "d5",
                  "d6", "d7", "d8", "c1", "c2", "c3", "c4", "c5", "c6"]}
VERSIONS = {"v1": "h1", "v2": "h2", "v3": "h3"}


def prompt(key: str, tags: dict) -> str:
    """One clip's words: context, what each picture is for, the shots, the look, the sound."""
    c = CLIPS[key]
    said = "; ".join(VOICE[v] for v in c["voices"])
    lines = [f"Scene context: {c['context']}", *[JOB[r] for r in c["refs"]], *c["extra"],
             *c["shots"], f"Look: {c['look']}",
             f"Sound: {c['sound']}" + (f" Voices: {said}." if said else "") + f" {END}"]
    return "\n".join(lines).format(**tags)


if __name__ == "__main__":
    total = 0
    for k, c in CLIPS.items():
        tags = {r: f"[{r}]" for r in JOB}
        p = prompt(k, tags)
        at = [s.split(",", 1)[1].split(":")[0].strip() for s in c["shots"]]
        end = float(at[-1].split("-")[1].split()[0])
        flag = "" if abs(end - c["seconds"]) < 0.01 else f"  <-- shots end at {end}"
        total += c["seconds"]
        print(f"{k:3} {c['seconds']:3}s {len(c['shots'])} shots {len(c['refs'])} pictures {len(p):5} chars{flag}")
    print("total", total, "s  = $%.2f at $0.14/s" % (total * 0.14))
