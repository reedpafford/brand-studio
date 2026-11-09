import { QueryClient } from "@tanstack/react-query";

/** The video page's own reads (each keyed by its video). The parts of that page open one after another, so one of
 *  these reads stays fresh for 3 s and the parts share it instead of each asking again (it asked for the same things
 *  2 to 5 times). The page's presses refresh what they change, and its polling and refreshes still read at once.
 *  Every other read keeps the default: asked again whenever a screen opens. */
export const VIDEO_PAGE = ["project", "idea", "director", "run-progress", "project-clips", "storyboard", "project-video", "project-cut", "asks", "cast", "assets", "breakdown", "script", "video-settings"];
export const SHARED_FOR = 3_000;

/** The app's cache (main.tsx, and the tests' renderApp). */
export function newQueryClient() {
  const client = new QueryClient();
  for (const key of VIDEO_PAGE) client.setQueryDefaults([key], { staleTime: SHARED_FOR });
  return client;
}
