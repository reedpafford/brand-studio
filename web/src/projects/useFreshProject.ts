import { useQueryClient } from "@tanstack/react-query";
import { useJobs } from "../clip/History";
import { useOnChange } from "../useOnChange";

/** The video's credits, budget and header follow its jobs: whenever one of its jobs changes (starts, finishes, fails and is paid back), the project is read again. */
export function useFreshProject(id: number) {
  const queryClient = useQueryClient();
  const jobs = useJobs(id);
  const state = jobs.data?.map((j) => `${j.id}:${j.status}`).join(",");
  useOnChange(state, () => {
    void queryClient.invalidateQueries({ queryKey: ["project", id] });
    void queryClient.invalidateQueries({ queryKey: ["idea", id] }); // the header's money and status (v6 S3)
  });
}
