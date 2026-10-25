import type { components } from "../api/schema";

export type Model = components["schemas"]["ModelOut"];
export type Settings = { aspect: string; duration: number; resolution: string };

/** Pull a model's settings into its limits. Returns the new settings and what changed, in plain words. */
export function fit(model: Model, s: Settings): { settings: Settings; notes: string[] } {
  const notes: string[] = [];
  const out = { ...s };
  const lo = model.duration?.min ?? 1;
  const hi = model.duration?.max ?? 30;
  if (out.duration > hi) {
    out.duration = hi;
    notes.push(`Length set to ${hi}s, the most ${model.name} allows.`);
  } else if (out.duration < lo) {
    out.duration = lo;
    notes.push(`Length set to ${lo}s, the least ${model.name} allows.`);
  }
  if (!model.resolutions.includes(out.resolution)) {
    out.resolution = model.resolutions[0];
    notes.push(`Quality set to ${out.resolution}.`);
  }
  if (!model.aspect_ratios.includes(out.aspect)) {
    out.aspect = model.aspect_ratios[0];
    notes.push(`Shape set to ${out.aspect}.`);
  }
  return { settings: out, notes };
}

export const defaultSettings = (model: Model): Settings =>
  fit(model, {
    aspect: "9:16",
    duration: Math.max(model.duration?.min ?? 4, Math.min(8, model.duration?.max ?? 8)),
    resolution: model.resolutions[0],
  }).settings;

export const clipCredits = (model: Model, s: Settings) =>
  Math.ceil((model.credits_per_unit[s.resolution] ?? 0) * s.duration);

export const fromRate = (model: Model) => Math.min(...Object.values(model.credits_per_unit));

/** True when the prompt mentions a screen's "always used for" moment ("buy-moment" matches "buy moment"). */
export const mentionsMoment = (prompt: string, moment: string) =>
  prompt.toLowerCase().replace(/[\s_-]+/g, " ").includes(moment.toLowerCase().replace(/[\s_-]+/g, " "));

/** The reason Generate is off, or null. First one that applies. */
export function blockedReason(a: {
  prompt: string;
  loading: boolean;
  tooMany: boolean;
  maxRefs: number;
  rendering: boolean;
  noEstimate?: boolean;
  refused?: string;
  alreadySent?: boolean;
}): string | null {
  if (a.loading) return "Loading a brand piece…";
  if (a.prompt.trim().length < 8) return "Describe the clip (8 or more characters)";
  if (a.tooMany) return `This model takes up to ${a.maxRefs} brand pieces. Remove some.`;
  if (a.rendering) return "A clip is already being made";
  if (a.alreadySent) return "Sent. Change something to send another.";
  if (a.refused) return a.refused;
  return a.noEstimate ? "Working out the cost…" : null;
}
