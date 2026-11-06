import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useJobs } from "../clip/History";

/** The video's credits, budget and header follow its jobs: whenever one of its jobs changes (starts, finishes, fails and is paid back), the project is read again. */
export function useFreshProject(id: number) {
  const queryClient = useQueryClient();
  const jobs = useJobs();
  const state = (jobs.data ?? []).filter((j) => j.project_id === id).map((j) => `${j.id}:${j.status}`).join(",");
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ["project", id] });
    void queryClient.invalidateQueries({ queryKey: ["idea", id] }); // the header's money and status (v6 S3)
  }, [state, id, queryClient]);
}
