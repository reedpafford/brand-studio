import type { ReactNode } from "react";

/** The Plan step (item 1b): Scenes (the scene plan) and Shots (what was the Breakdown step). The page gives it the Shots view;
 *  the Scenes view and the Scenes | Shots switch are Next-Screens' (flows P1), shown once the video carries its plan status. */
export function PlanStep({ shots }: { shots: ReactNode }) {
  return <>{shots}</>;
}
