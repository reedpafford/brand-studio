import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Banner, Button, wholeCredits } from "../components";

const START_IN = 5;
const key = (projectId: number) => `brand-studio:no-auto-looks:${projectId}`;
const turnedDown = (projectId: number) => {
  try {
    return sessionStorage.getItem(key(projectId)) === "1";
  } catch {
    return false;
  }
};

/** "Nate, Mia and the Rival". */
const names = (roles: string[]) => (roles.length <= 1 ? roles.join("") : `${roles.slice(0, -1).join(", ")} and ${roles[roles.length - 1]}`);

/** Missing looks of main and recurring roles are made on their own (video-flow.md): the price first, a short countdown, Not now to stop it.
 *  It only starts when all of it fits the budget or the editor's week; otherwise the server's reason is shown and the cards keep their own buttons. */
export function AutoLooks({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const [no, setNo] = useState(() => turnedDown(projectId));
  const [left, setLeft] = useState(START_IN);
  const [made, setMade] = useState<{ n: number; credits: number } | null>(null);
  const [began, setBegan] = useState(false); // it starts once per visit
  const missing = useQuery({
    queryKey: ["missing-looks", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/assets/missing-looks", { params: { path: { project_id: projectId } } })).data ?? null,
  });
  const m = missing.data;
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/assets/missing-looks", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async () => {
      setMade({ n: m?.slot_ids.length ?? 0, credits: m?.credits ?? 0 });
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["assets", projectId] }), queryClient.invalidateQueries({ queryKey: ["missing-looks", projectId] })]);
    },
  });
  const ready = !!m && m.slot_ids.length > 0 && !m.reason && !no && !make.isPending && !began;
  useEffect(() => {
    if (!ready) return;
    const t = setTimeout(() => {
      if (left > 1) return setLeft(left - 1);
      setLeft(0);
      setBegan(true);
      make.mutate();
    }, 1000);
    return () => clearTimeout(t);
  }, [ready, left]); // eslint-disable-line react-hooks/exhaustive-deps

  const notNow = () => {
    setNo(true);
    try {
      sessionStorage.setItem(key(projectId), "1");
    } catch {
      /* private window: it only lasts until the page is left */
    }
  };
  if (make.isError) return <Banner tone="warning" title={make.error.message} />;
  if (make.isPending) return <Banner tone="info" title={`Making looks for ${names(m?.roles ?? [])} · ${wholeCredits(m?.credits ?? 0)} credits`} />;
  if (made && made.n > 0) return <Banner tone="info" title={`Made ${made.n} look${made.n === 1 ? "" : "s"} · ${wholeCredits(made.credits)} credits. Check each one, then approve.`} />;
  if (!m || m.slot_ids.length === 0) return null;
  if (m.reason) return <Banner tone="warning" title={m.reason} />;
  if (no) return null;
  return (
    <Banner
      tone="info"
      title={`Making looks for ${names(m.roles)} · ${wholeCredits(m.credits)} credits`}
      action={
        <Button variant="ghost" onClick={notNow}>
          Not now
        </Button>
      }
    >
      Starting in {Math.max(left, 0)} s
    </Banner>
  );
}
