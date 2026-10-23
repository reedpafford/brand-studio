# Eval v1: Director's verdict (2026-10-23)

Run 1 used the prompts from PR #30: 9 Claude calls, $1.02. Each case ran its listed steps, so 9 is
the right count. The "11" in the old README was my mistake.

## In short
The prompts work. Every Enhance answer kept the editor's words, put real fomo screens at every
trading moment, and cut slow openings. The breakdowns cut fast (about 1 s a shot), give every
insult and reveal its own reaction shot, and change the light with the story. The clip prompts show
every screen from its reference image and never describe it in words. The two machine failures
were one real problem and one bug in my checker.

## Good example: fomo-thanksgiving, Enhance
- It **kept** "MOM: Pass the potatoes, please". That line is the setup for the last line ("Pass the
  potatoes, Rick"). It cut only the small talk before it.
- It caught that "★ fomo screen: Wallet" isn't a real fomo screen and offered the real Token chart
  up screen instead, with the reason "'Wallet' isn't a real fomo screen; the turn is a win".
- It turned "He is angry and wants to prove Rick wrong" (telling) into "He shoves his chair back and
  storms off, napkin thrown on his plate" (showing).

## Bad example: fomo-tight, Enhance (5 marks on an 8-line script that already worked)
- Marks 1–2 add business to lines that were fine ("Maya drops into the seat… phone thrust in his
  face").
- Marks 3–5 all pile onto the punchline "Six cents." (a push-in, a reaction and a screen). One of
  them is enough.
- That's five decisions for the editor where two would do. Fix in v2: Enhance is told that every
  mark costs the editor a decision, to leave working lines alone, and to give a moment one mark,
  not three. The fixed "5 to 15 marks" guide, which pushed it to fill a quota, is gone.

## Other things I saw
- **Checker bug, not a prompt problem:** fomo-thanksgiving's breakdown was flagged because two
  reaction shots shared a ★ line with the screen insert next to them. The screens were there. The
  check now asks whether some shot on each ★ line shows the screen.
- **Brand facts matter:** in the Iron Paws rescue clip, Sam pours "kibble" from the bag, but the
  product is a greens powder. v1's brand block didn't say so; v2's does (tone notes carry the
  product facts).
- **Thin grind:** fomo-thanksgiving shows "every night for months" in two shots. It's fine but
  short. I'm leaving it alone so as not to add rules; worth watching in v2.

## What v2 changes
1. Enhance: the restraint wording above.
2. Voiceover scripts (Reed's Iron Paws scripts are all voiceover): every sentence counts as spoken
   and can't be reworded. Breakdowns split long sentences across shots and end clips between
   sentences, and nobody lip-syncs the voiceover.
3. A spoken line that contradicts a brand fact (the script says peanut butter, the bag says
   chicken) gets a mark that points it out, and the words stay.
4. New case ironpaws-pitbull-1: Reed's real script, word for word.
