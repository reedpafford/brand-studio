# Step: Cast slots
<!-- Inputs: one <version slot="N"> per approved version (0 is the original, then 1 and 2), numbered; optional <reference> (the reel the script adapts). Output: CastSlots. -->

Read every version and list the **cast slots**: each role the videos need a look for, so one sheet per slot can be drawn or picked and used in every version it appears in. You only list roles; you never change a script.

Who is a slot:
- the main characters, and every named role;
- helpers (a mentor, a coach, a best friend, including one from the <reference> that a version keeps), rivals (the richer man she leaves with), and family;
- an animal that is a character (the pitbull who narrates).

Who never is:
- background people: guests, crowds, admirers, extras, onlookers;
- one-shot functional people who are just a hand or a pass-by: the courier, the dealer handing over keys, a waiter.

One role is one slot across versions. The same person under the same name is one slot, and `appears_in` lists every version slot they're in. A role that only one variation adds gets its own slot listing just that version. List the mains first, then the rest in order of first appearance.

For each slot:
- `role` is the script's name and part ("Nate, the groom", "Bruno, the pitbull (narrator)"). An unnamed role goes by its part ("His owner", "The rich rival").
- `description` is a short look that fits every version: age, build, hair or coat, skin tone, signature outfit ("17, lanky, light brown skin, short twists, grey hoodie and red beanie"). It must be plain and drawable: no celebrity look-alikes, no brand logos on clothes. Keep what the scripts say: if a script gives an age, a colour or an outfit, use it.
- `recurring` is true when the role is in two or more scenes or versions.
