import { useState } from "react";
import { RotateCcw, Sparkles } from "lucide-react";
import { Button, Card, Dialog, Skeleton } from "../components";
import { errorText as errorClass } from "../ui";
import { useFindRoles } from "./useCast";

/** "Claude can find the roles in your script." when there are none; "Find roles again" (after a confirm) when there are. */
export function FindRoles({ scriptId, hasRoles }: { scriptId: number; hasRoles: boolean }) {
  const find = useFindRoles(scriptId);
  const [asking, setAsking] = useState(false);
  const failed = !find.running && (find.start.isError || find.problems.length > 0);
  const button = (again: boolean) => (
    <Button variant={again ? "ghost" : "primary"} icon={again ? RotateCcw : Sparkles} price={find.price} busy={find.start.isPending} disabled={find.price === undefined} onClick={() => (again ? setAsking(true) : find.start.mutate())}>
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
        {button(true)}
        {asking && (
          <Dialog title="Find the roles again?" cancelLabel="Not now" actionLabel="Find roles" busy={find.start.isPending} onCancel={() => setAsking(false)} onConfirm={() => find.start.mutate(undefined, { onSettled: () => setAsking(false) })}>
            Locked roles stay locked; roles you added stay.
          </Dialog>
        )}
        {failed && <p role="alert" className={errorClass}>The roles weren't found. Nothing was charged.</p>}
      </>
    );
  return (
    <Card className="max-w-[680px] space-y-3">
      <p>Claude can find the roles in your script.</p>
      {failed && (
        <p role="alert" className={errorClass}>
          The roles weren't found. Nothing was charged. {find.start.isError ? find.start.error.message : ""}
        </p>
      )}
      {button(false)}
    </Card>
  );
}
