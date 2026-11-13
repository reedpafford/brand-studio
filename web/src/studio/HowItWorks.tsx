import { useState } from "react";
import { Pencil } from "lucide-react";
import { itemWords, useSaveItem } from "../library/itemActions";
import type { Item } from "../library/kinds";

/** "How it works": a product's own notes, the words the director is given with the product in every video. They are
 *  shown and edited as plain text, exactly as stored: never split, trimmed or tidied, here or on the way back. Nothing
 *  is sent until Save, and Save sends what is in the box, as it is (the current site's own save of the same field). */
export function HowItWorks({ item }: { item: Item }) {
  const [text, setText] = useState<string | null>(null); // null: reading, not editing
  const save = useSaveItem("prop", item.id);
  return (
    <section className="how" aria-label="How it works">
      <h3>How it works</h3>
      {text === null ? (
        <>
          {item.notes ? <p className="words">{item.notes}</p> : <p className="hint">Nothing written yet. Say how it is used and what happens when it is, in your own words.</p>}
          <button type="button" className="btn soft" onClick={() => (save.reset(), setText(item.notes))}>
            <Pencil size={14} strokeWidth={1.75} aria-hidden />
            {item.notes ? "Edit" : "Write it"}
          </button>
        </>
      ) : (
        <>
          <textarea aria-label="How it works" autoFocus rows={6} value={text} onChange={(e) => setText(e.target.value)} />
          {save.isError && (
            <p className="hint bad" role="alert">
              {save.error.message}
            </p>
          )}
          <div className="offers">
            <button type="button" className="btn soft" disabled={text === item.notes || save.isPending} onClick={() => save.mutate({ ...itemWords(item), notes: text }, { onSuccess: () => setText(null) })}>
              Save
            </button>
            <button type="button" className="btn ghost" onClick={() => setText(null)}>
              Cancel
            </button>
          </div>
        </>
      )}
      <p className="hint">The director reads these words with the product, exactly as written.</p>
    </section>
  );
}
