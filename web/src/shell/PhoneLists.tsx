import { ArrowLeft, ChevronRight, FileText, Images, Palette, Users, type LucideIcon } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { AccountMenu, STUDIO, useSignOut } from "./AccountMenu";

const rowClass = "flex min-h-12 w-full items-center gap-3 border-b border-border px-4 text-left text-md";

function Row({ to, label, Icon }: { to: string; label: string; Icon: LucideIcon }) {
  return (
    <Link to={to} className={rowClass}>
      <Icon size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
      <span className="flex-1">{label}</span>
      <ChevronRight size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
    </Link>
  );
}

function List({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="min-h-screen">
      <h1 className="flex h-14 items-center border-b border-border bg-surface px-4 text-lg font-semibold">{title}</h1>
      <div className="bg-surface">{children}</div>
    </main>
  );
}

/** The phone's Library tab (S-gaps-04 R3): the same pages the rail's Library opens. */
export function LibraryList() {
  const b = `/b/${useParams().brandId}`;
  return (
    <List title="Library">
      <Row to={`${b}/scripts`} label="Scripts" Icon={FileText} />
      <Row to={`${b}/library`} label="Cast & places" Icon={Users} />
      <Row to={`${b}/media`} label="Media" Icon={Images} />
      <Row to={`${b}/brand`} label="Brand kit" Icon={Palette} />
    </List>
  );
}

/** The phone's More tab (S-gaps-04 R3): the owner's Studio rows, then the account. An editor has no Studio rows. */
export function MoreList() {
  const owner = useMe().data?.role === "owner";
  const signOut = useSignOut();
  return (
    <List title="More">
      {owner && STUDIO.map(([to, label, Icon]) => <Row key={to} to={to} label={label} Icon={Icon} />)}
      {owner && <div aria-hidden className="h-2 bg-surface-2" />}
      <AccountMenu row />
      <button type="button" onClick={() => signOut.mutate()} className={rowClass}>
        <ArrowLeft size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
        <span className="flex-1">Sign out</span>
        <ChevronRight size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
      </button>
    </List>
  );
}
