/** Problems that stop a step: everything but advice ("Advice: …" is shown but never blocks). */
export const blocking = (problems: string[]) => problems.filter((p) => !p.startsWith("Advice: "));
