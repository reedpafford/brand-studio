import { useState, type ReactNode } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "../components";
import { lookName, useLooks } from "../scripts/Looks";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { useFreestyleActions, useTypeName, type Freestyle, type Settings } from "./useFreestyle";

/** A freestyle's settings in words, for the tags on its first message. */
export function useSettingsWords() {
  const looks = useLooks().data;
  const brands = useBrands().data;
  const typeName = useTypeName();
  return (s: Settings) => [typeName(s.type), lookName(looks, s.look), s.shape, brands?.find((b) => b.id === s.brand_id)?.name ?? "No brand"];
}

/** The one press of New video and Make a video: the owner's makes it at once, an editor's goes to the owner; both carry
 *  their cap ("up to N credits", rule 34) once it's known, and ⌘↵. */
export function SendPress({ owner, price, busy, disabled, wide, onClick }: { owner: boolean; price: number | undefined; busy: boolean; disabled: boolean; wide?: boolean; onClick?: () => void }) {
  return (
    <Button type={onClick ? "button" : "submit"} busy={busy} disabled={disabled} kbd={wide ? undefined : "⌘↵"} onClick={onClick} className={wide ? "w-full" : "shrink-0 whitespace-nowrap lg:px-3 lg:text-sm"} price={disabled ? undefined : price} charge="estimate">
      {owner ? "Make it" : "Send for approval"}
    </Button>
  );
}

/** The change box under an older freestyle's thread: "Tell the director what to change", the status line and the send
 *  arrow. Enter sends, Shift+Enter is a new line. An editor's change goes to the owner. */
export function ChangeBox({ fs, status }: { fs: Freestyle; status: ReactNode }) {
  const [text, setText] = useState("");
  const change = useFreestyleActions(fs.id).change;
  const go = () => text.trim() && !change.isPending && change.mutate(text.trim(), { onSuccess: () => setText("") });
  const rail = useRail();
  const said = (
    <p className="text-sm text-muted" role="status">
      {change.isError ? <span className="text-danger">{change.error.message}</span> : status}
    </p>
  );
  const send = <Button type="submit" variant="secondary" dense icon={ArrowUp} busy={change.isPending} disabled={!text.trim()} aria-label="Send the change" />;
  // On a phone (B_PhoneVideo): the line above, then a one-line box with the send beside it.
  return (
    <form
      aria-label="Your change"
      className={rail ? "flex flex-col gap-2 rounded-lg border border-border-strong bg-surface p-3 focus-within:border-focus" : "space-y-2"}
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      {!rail && said}
      <label htmlFor={`change-${fs.id}`} className="sr-only">
        Tell the director what to change
      </label>
      <div className={rail ? "contents" : "flex items-center gap-2"}>
      <textarea
        id={`change-${fs.id}`}
        rows={rail ? 2 : 1}
        maxLength={2000}
        value={text}
        placeholder="Tell the director what to change"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            go();
          }
        }}
        className={rail ? "min-h-10 resize-none bg-transparent px-0.5 text-base outline-none! placeholder:text-faint" : "min-h-control min-w-0 flex-1 resize-none rounded-md border border-border-strong bg-surface px-3 py-2.5 text-base placeholder:text-faint"}
      />
      {!rail && send}
      </div>
      {rail && (
        <div className="flex items-center justify-between gap-3">
          {said}
          {send}
        </div>
      )}
    </form>
  );
}
