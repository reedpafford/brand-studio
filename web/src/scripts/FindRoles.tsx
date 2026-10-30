import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, RotateCcw, Sparkles } from "lucide-react";
import { api, errorText } from "../api/client";
import { Button, Card, Dialog, Skeleton, useToast } from "../components";
import { errorText as errorClass } from "../ui";
import { useFindRoles } from "./useCast";
import { useAllowanceStop, type Script } from "./useScript";

/** "Claude can find the roles in your script." when there are none; "Find roles again" (after a confirm) when there are. */
export function FindRoles({ script, hasRoles }: { script: Script; hasRoles: boolean }) {
  const scriptId = script.id;
  const find = useFindRoles(scriptId);
  const stop = useAllowanceStop(script, find.price);
  const approved = script.versions.find((v) => v.slot === 0)?.status === "approved";
  const reason = !approved ? "Approve the words first" : stop;
  // The roles are read from the approved words. A script with no variations is approved here: it is the only version.
  const queryClient = useQueryClient();
  const toast = useToast();
  const setApproval = useMutation({
    mutationFn: async (yes: boolean) => {
      const args = { params: { path: { script_id: scriptId, slot: 0 } } };
      const { data, error } = yes ? await api.POST("/scripts/{script_id}/drafts/{slot}/approve", args) : await api.DELETE("/scripts/{script_id}/drafts/{slot}/approve", args);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data, yes) => {
      queryClient.setQueryData(["script-lib", scriptId], data);
      void queryClient.invalidateQueries({ queryKey: ["scripts"] });
      if (yes) toast("Words approved. They're final.", () => setApproval.mutate(false));
    },
  });
  const approveIt = !approved && (
    <div className="space-y-1">
      <p className="text-sm text-muted">Claude reads the roles from the approved words. Approving makes them final; you can undo it.</p>
      <Button variant="secondary" icon={Check} busy={setApproval.isPending} onClick={() => setApproval.mutate(true)}>
        Approve the words
      </Button>
      {setApproval.isError && <p role="alert" className={errorClass}>{setApproval.error.message}</p>}
    </div>
  );
  const [asking, setAsking] = useState(false);
  // A refused start says why; "weren't found" is only for a read that ran and found nothing.
  const refused = !find.running && find.start.isError ? find.start.error.message : null;
  const failed = !find.running && !refused && !hasRoles && find.problems.length > 0;
  const button = (again: boolean) => (
    <Button variant={again ? "ghost" : "secondary"} icon={again ? RotateCcw : Sparkles} charge="estimate" price={find.price} busy={find.start.isPending} disabled={find.price === undefined || reason !== null} reason={reason} onClick={() => (again ? setAsking(true) : find.start.mutate())}>
      {again ? "Find roles again" : failed ? "Try again" : "Find roles in the script"}
    </Button>
  );
  if (find.running)
    return (
      <div role="status" className="space-y-2">
        <p className="text-muted">Finding the roles…</p>
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    );
  if (hasRoles)
    return (
      <>
        {approveIt}
        {button(true)}
        {asking && (
          <Dialog title="Find the roles again?" cancelLabel="Not now" actionLabel="Find roles" busy={find.start.isPending} onCancel={() => setAsking(false)} onConfirm={() => find.start.mutate(undefined, { onSettled: () => setAsking(false) })}>
            Locked roles stay locked; roles you added stay.
          </Dialog>
        )}
        {refused && <p role="alert" className={errorClass}>{refused}</p>}
      </>
    );
  return (
    <Card className="max-w-[680px] space-y-3">
      <p>Claude can find the roles in your script.</p>
      {approveIt}
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {failed && <p role="alert" className={errorClass}>The roles weren't found. Nothing was charged.</p>}
      {button(false)}
    </Card>
  );
}
