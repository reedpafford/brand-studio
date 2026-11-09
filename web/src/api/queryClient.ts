import { QueryClient } from "@tanstack/react-query";

/** The app's cache (main.tsx, and the tests' renderApp). A read is fresh for 3 s: the parts of a page that open one after
 *  another share what the first one read instead of each asking again (a video's page asked for the same things 2 to 5
 *  times). Polling and a press's refresh still read at once. */
export const newQueryClient = () => new QueryClient({ defaultOptions: { queries: { staleTime: 3_000 } } });
