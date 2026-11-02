// What a request makes, in plain words (the row names the video beside it).
export const STEPS: Record<string, string> = {
  enhance: "Script suggestions",
  script_draft: "A script draft",
  breakdown: "The breakdown",
  storyboard: "The storyboard",
  frame: "A new still",
  clip_prompts: "The clip prompts",
  clip_take: "A new take",
  sheet: "A character's look",
  improve: "A better prompt",
  director: "The director's next move",
  song_take: "Songs, narration or music on a script",
  // As the server names them (needs_you.NAMES), for every step an editor's press can be held on (QA-5 on #1114).
  plan: "The scene plan",
  plan_scene: "A scene",
  song_breakdown: "The shot plan",
  narrated_breakdown: "The shot plan",
  stills: "The stills",
  change: "A change",
  variations: "Variations",
};
// Names that are plural, so a line about them reads "are" ("The clip prompts are being made").
export const PLURAL = new Set(["Script suggestions", "The clip prompts", "The stills", "Variations"]);
