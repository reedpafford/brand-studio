import { changedSnippets, Words } from "./ChangeBox";

/** What a free rewrite changed, in the changed words only, with a few around each: "Before: …" and "After: …". */
export function BeforeAfter({ before, after, label }: { before: string; after: string; label: string }) {
  const snippets = changedSnippets(before, after);
  if (snippets.length === 0) return null;
  return (
    <div className="space-y-1 text-sm" aria-label={label}>
      {snippets.map((s, i) => (
        <p key={i}>
          <span className="font-medium">Before: </span>
          <Words parts={s.before} />
          <br />
          <span className="font-medium">After: </span>
          <Words parts={s.after} />
        </p>
      ))}
    </div>
  );
}
