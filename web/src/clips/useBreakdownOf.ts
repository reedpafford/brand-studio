import { useQuery } from "@tanstack/react-query";
import { readBreakdown } from "../projects/BreakdownPane";

/** The video's newest shots and clips (its scenes and what each clip shows), or null before there are any. */
export function useBreakdownOf(projectId: number) {
  return useQuery({
    queryKey: ["breakdown", projectId, "clips"],
    enabled: projectId > 0,
    queryFn: () => readBreakdown(projectId),
  });
}
