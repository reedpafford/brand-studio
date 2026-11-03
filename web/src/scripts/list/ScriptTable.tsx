import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { FolderOut } from "../../folders/Projects";
import { TableHead, type Row } from "./ScriptRow";

/** Scripts as a table (v5 C_Scripts, E_EditorScripts): one header, then a row per script, on hairlines, edge to edge. */
export function ScriptTable({ rows, row, editor }: { rows: Row[]; row: (r: Row) => ReactNode; editor?: boolean }) {
  return (
    <div className="-mx-4 sm:-mx-6">
      <TableHead editor={editor} />
      <ul>{rows.map(row)}</ul>
    </div>
  );
}

/** The scripts grouped by project under one header: each project is a quiet bar with its name and count that opens and
 *  closes; No project comes last and starts closed when another group has scripts. With no projects it is the one table. */
export function ProjectGroups({ rows, folders, row }: { rows: Row[]; folders: FolderOut[] | null | undefined; row: (r: Row) => ReactNode }) {
  const groups = (folders ?? []).map((f) => ({ key: String(f.id), name: f.name, rows: rows.filter((r) => r.folder_id === f.id) })).filter((g) => g.rows.length > 0);
  const known = new Set((folders ?? []).map((f) => f.id));
  const loose = rows.filter((r) => r.folder_id == null || !known.has(r.folder_id)); // a deleted project's scripts read as No project
  const [open, setOpen] = useState<Record<string, boolean>>({});
  // With no projects yet there is still the one group bar, "No project 17" (C_Scripts), open since it's all there is.
  const all = [...groups, ...(loose.length ? [{ key: "none", name: "No project", rows: loose }] : [])];
  return (
    <div className="-mx-4 sm:-mx-6">
      <TableHead />
      {all.map((g) => {
        const shown = open[g.key] ?? (g.key !== "none" || groups.length === 0);
        const Icon = shown ? ChevronDown : ChevronRight;
        return (
          <section key={g.key} aria-label={g.name}>
            <h2 className="border-b border-border bg-surface">
              <button type="button" aria-expanded={shown} onClick={() => setOpen({ ...open, [g.key]: !shown })} className="flex min-h-control w-full items-center gap-2 px-4 text-left text-sm font-medium sm:px-6 lg:min-h-[34px]">
                <Icon size={14} strokeWidth={2} aria-hidden className="text-muted" />
                {g.name} <span className="text-xs font-normal tabular-nums text-muted">{g.rows.length}</span>
              </button>
            </h2>
            {shown && <ul>{g.rows.map(row)}</ul>}
          </section>
        );
      })}
    </div>
  );
}
