import type { components } from "../api/schema";

type Facts = components["schemas"]["RoleFacts"] | null | undefined;

/** "Late 20s (a guess) · woman · nurse": a role's age range, gender and what they do. A fact the script didn't say but was worked out is marked "(a guess)". Nothing at all when no fact is known. */
export function RoleFacts({ facts }: { facts: Facts }) {
  const parts = [facts?.age_range, facts?.gender, facts?.occupation].filter((f): f is NonNullable<typeof f> => !!f && !!f.value);
  if (parts.length === 0) return null;
  return (
    <p className="text-sm text-muted">
      {parts.map((f, i) => (
        <span key={i}>
          {i > 0 && " · "}
          {f.value}
          {f.inferred && <span className="text-faint"> (a guess)</span>}
        </span>
      ))}
    </p>
  );
}
