/** A shot shows the wrong person's look (the server's cast check). It stops stills until it is fixed or kept. */
export const CAST = "Check the cast: ";

/** Problems that stop a step: everything but advice ("Advice: …" is shown but never blocks), and a cast problem the person kept anyway. */
export const blocking = (problems: string[], kept: string[] = []) => problems.filter((p) => !p.startsWith("Advice: ") && !(p.startsWith(CAST) && kept.includes(p)));
