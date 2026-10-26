# Step: Cast slots
<!-- Inputs: optional <brief> (the script's title and description), optional <cast> (characters already in the cast: id, name and part), one <version slot="N"> per approved version (0 is the original, then 1 and 2), numbered; optional <reference> (the reel the script adapts). Output: CastSlots. -->

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
- `role` carries the role's name whenever <cast> or a script gives one: "Nate, the groom"; "Bruno, the pitbull (narrator)" even when the voiceover only ever says "I". A narrator named in <cast> keeps that name. Only a role nobody names goes by its part ("His owner", "The rich rival").
- `description` **starts with who they are: an age range, a gender and a role or job** ("Mid-40s woman, a primary-school teacher; …", "17-year-old boy, a student; …", "2-year-old male pitbull, the family dog; …"), every time, so a sheet can never draw a teacher as a child. When the scripts and the brief don't say one of these, infer it from the story (who they are to the hero, what they do, how they talk) and list it in `guessed` (`["age", "occupation"]`), so the editor sees it's a guess. Then it  what <cast>, <brief>, the scripts and <reference> say (the breed, the age, a signature item: Bruno is a pitbull, so he's drawn as one), and only then fills in the rest. It is a short look that fits every version: age, build, hair or coat, skin tone, signature outfit ("17-year-old boy, a student; lanky, light brown skin, short twists, grey hoodie and red beanie"). It must be plain and drawable: no celebrity look-alikes, no brand logos on clothes. Keep what the scripts say: if a script gives an age, a colour or an outfit, use it.
- `kind` is Main (the hero, and the story's other lead), Helper (a mentor, coach or friend), Rival (the one they're up against: the richer man, the doubter who bets against them), or Family (a parent, an aunt, a sibling). A doubting aunt is Family; pick the role's relation, not its mood.
- `recurring` is true when the role is in two or more scenes or versions.
