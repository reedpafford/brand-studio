import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card } from "../../components";
import type { FolderOut } from "../../folders/Projects";
import { TableHead, type Row } from "./ScriptRow";

/** Scripts as a table: one header, then a row per script. */
export function ScriptTable({ rows, row }: { rows: Row[]; row: (r: Row) => ReactNode }) {
  return (
    <Card className="p-0 sm:p-0">
      <TableHead />
      <ul className="divide-y divide-border">{rows.map(row)}</ul>
    </Card>
  );
}

/** The scripts grouped by project, each with its name and count; No project starts closed when another group has scripts.
 *  With no projects made yet it is the one table. */
export function ProjectGroups({ rows, folders, row }: { rows: Row[]; folders: FolderOut[] | null | undefined; row: (r: Row) => ReactNode }) {
  const groups = (folders ?? []).map((f) => ({ key: String(f.id), name: f.name, rows: rows.filter((r) => r.folder_id === f.id) })).filter((g) => g.rows.length > 0);
  const known = new Set((folders ?? []).map((f) => f.id));
  const loose = rows.filter((r) => r.folder_id == null || !known.has(r.folder_id)); // a deleted project's scripts read as No project
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (groups.length === 0) return <ScriptTable rows={rows} row={row} />;
  const all = [...groups, ...(loose.length ? [{ key: "none", name: "No project", rows: loose }] : [])];
  return (
    <>
      {all.map((g) => {
        const shown = open[g.key] ?? g.key !== "none";
        const Icon = shown ? ChevronDown : ChevronRight;
        return (
          <section key={g.key} aria-label={g.name} className="space-y-2">
            <h2 className="type-section">
              <button type="button" aria-expanded={shown} onClick={() => setOpen({ ...open, [g.key]: !shown })} className="inline-flex min-h-control items-center gap-2 rounded-md pr-2 hover:bg-surface-2">
                <Icon size={16} strokeWidth={1.75} aria-hidden />
                {g.name} <span className="font-normal text-muted tabular-nums">· {g.rows.length}</span>
              </button>
            </h2>
            {shown && <ScriptTable rows={g.rows} row={row} />}
          </section>
        );
      })}
    </>
  );
}
