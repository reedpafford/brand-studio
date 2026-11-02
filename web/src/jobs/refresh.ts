import type { QueryClient } from "@tanstack/react-query";

/** Ask for the jobs list again after a press. A first load still in flight is cancelled first: invalidating alone
 *  hands back that same request (TanStack only cancels a fetch that already has data), whose answer predates the
 *  press, so polling never starts and the new job never shows. */
export async function refreshJobs(queryClient: QueryClient) {
  await queryClient.cancelQueries({ queryKey: ["jobs"] });
  return queryClient.invalidateQueries({ queryKey: ["jobs"] });
}
