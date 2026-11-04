import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Banner, Button, Dialog, Field, PageTop, Panel, Select, Skeleton } from "../components";
import type { components } from "../api/schema";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { restoreMember, setRole, useRemovedMembers } from "./memberActions";
import { serverTime } from "../time";

const day = (iso: string) => serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const ROLE = { owner: "Owner", editor: "Editor" } as const;
type NewInvite = components["schemas"]["NewInviteOut"];
/** v5 D_Team: Name | Email | Role | Last active | Remove. On a phone each row stacks. */
const grid = "grid grid-cols-2 items-center gap-x-4 gap-y-2 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1.4fr)_140px_140px_120px] sm:px-1";
/** "now", "4 min ago", "3 h ago", "yesterday", or the date (#1247 keeps it to within 5 minutes). */
export function lastActive(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return "Not yet";
  const mins = Math.floor((now - serverTime(iso).getTime()) / 60_000);
  if (mins < 5) return "now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 24 * 60) return `${Math.floor(mins / 60)} h ago`;
  if (mins < 48 * 60) return "yesterday";
  return day(iso);
}

function Avatar({ name, faded }: { name: string; faded?: boolean }) {
  return (
    <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-full bg-surface-3 text-[11px] font-semibold ${faded ? "opacity-60" : ""}`}>
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

export function TeamPage() {
  const { data: me } = useMe();
  const isOwner = me?.role === "owner";
  const rail = useRail();
  const toast = useToast();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["team"] });
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<{ id: number; name: string } | null>(null);
  const [changing, setChanging] = useState<{ id: number; name: string; to: "owner" | "editor" } | null>(null);
  const [fresh, setFresh] = useState<NewInvite | null>(null); // the link just made: it can only be shown now (only a hash is kept)
  const removed = useRemovedMembers(isOwner);
  const back = async (m: { id: number; name: string }, message: string) => {
    try {
      await restoreMember(m.id);
      await refresh();
      toast(message);
    } catch (e) {
      toast((e as Error).message, undefined, "error");
    }
  };
  const change = useMutation({
    mutationFn: async (c: { id: number; name: string; to: "owner" | "editor" }) => {
      await setRole(c.id, c.to);
      return c;
    },
    onSuccess: async (c) => {
      setChanging(null);
      await refresh();
      toast(`${c.name} is now ${c.to === "owner" ? "an owner" : "an editor"}.`, async () => {
        await setRole(c.id, c.to === "owner" ? "editor" : "owner");
        await refresh();
      });
    },
  });

  const members = useQuery({
    queryKey: ["team", "members"],
    queryFn: async () => {
      const { data } = await api.GET("/team/members");
      if (!data) throw new Error("members");
      return data;
    },
  });
  const invites = useQuery({
    queryKey: ["team", "invites"],
    enabled: isOwner,
    queryFn: async () => (await api.GET("/team/invites")).data ?? [],
  });
  const remove = useMutation({
    mutationFn: async (m: { id: number; name: string }) => {
      const { response } = await api.DELETE("/team/members/{member_id}", { params: { path: { member_id: m.id } } });
      if (!response.ok) throw new Error("remove");
      return m;
    },
    onSuccess: async (m) => {
      setRemoving(null);
      await refresh();
      toast(`${m.name} removed.`, () => void back(m, `${m.name} is back on the team.`));
    },
    onError: () => setRemoving(null),
  });
  const cancel = useMutation({
    mutationFn: (id: number) => api.DELETE("/team/invites/{invite_id}", { params: { path: { invite_id: id } } }),
    onSuccess: async () => {
      await refresh();
      toast("Invite cancelled.");
    },
  });
  const invite = isOwner && <Button onClick={() => setInviting(true)}>Invite someone</Button>;
  const onlyMe = members.data?.length === 1;
  const gone = removed.data ?? [];
  const waiting = (invites.data ?? []).filter((i) => i.id !== fresh?.id); // the one just made is in the card above

  return (
    <main className="space-y-6 p-4 sm:p-6">
      <PageTop title="Team">{invite && rail && invite}</PageTop>
      <div className="max-w-[1036px] space-y-6 sm:px-2">
      {invite && !rail && <ActionBar phone>{invite}</ActionBar>}
      {(members.isError || remove.isError) && (
        <Banner title={remove.isError ? "Couldn't remove that person." : "Couldn't load the team."} action={members.isError ? <Button variant="secondary" onClick={() => void members.refetch()}>Try again</Button> : undefined}>
          {remove.isError ? "Try again." : "Check your connection."}
        </Banner>
      )}
      {isOwner && <EditorLink />}
      {fresh && <FreshLink invite={fresh} />}
      <section className="space-y-2" aria-label="People">
        <h2 className="text-[15px] font-semibold">{members.data ? `People · ${members.data.length}` : "People"}</h2>
        {members.isPending && (
          <div className="space-y-2" aria-label="Loading">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        )}
        {members.data && (
          <div role="table" aria-label="People" className="text-sm">
            <div role="row" className={`${grid} hidden h-[34px] border-b border-border text-xs text-muted sm:grid`}>
              <span role="columnheader">Name</span>
              <span role="columnheader">Email</span>
              <span role="columnheader">Role</span>
              <span role="columnheader">Last active</span>
              <span role="columnheader"><span className="sr-only">Remove</span></span>
            </div>
            {members.data.map((m) => {
              const mine = isOwner && m.id !== me?.id;
              return (
                <div role="row" key={m.id} className={`${grid} border-b border-border py-2 sm:min-h-[50px] sm:py-0`}>
                  <span role="cell" className="flex min-w-0 items-center gap-2">
                    <Avatar name={m.name} />
                    <span className="truncate font-medium">{m.name}</span>
                  </span>
                  <span role="cell" className="min-w-0 truncate text-muted">{m.email}</span>
                  <span role="cell">
                    {mine ? (
                      <span className="relative block sm:w-[120px]">
                        <select
                          aria-label={`${m.name}'s role`}
                          value={m.role}
                          onChange={(e) => setChanging({ id: m.id, name: m.name, to: e.target.value as "owner" | "editor" })}
                          className="min-h-control w-full appearance-none rounded-md border border-border-strong bg-bg pl-2.5 pr-8 lg:min-h-control-dense"
                        >
                          <option value="editor">Editor</option>
                          <option value="owner">Owner</option>
                        </select>
                        <ChevronDown size={14} strokeWidth={2} aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" />
                      </span>
                    ) : (
                      <span className="text-muted">{ROLE[m.role as keyof typeof ROLE] ?? m.role}</span>
                    )}
                  </span>
                  <span role="cell" className="text-muted">
                    <span className="sm:hidden">Last active </span>
                    {lastActive(m.last_active_at)}
                  </span>
                  <span role="cell">
                    {mine && (
                      <Button variant="ghost" dense aria-label={`Remove ${m.name}`} onClick={() => setRemoving({ id: m.id, name: m.name })} className="w-full text-muted! sm:w-auto">
                        Remove
                      </Button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        {isOwner && onlyMe && <p className="text-sm text-muted">Invite your editors so they can make videos.</p>}
      </section>
      {isOwner && waiting.length > 0 && (
        <section className="space-y-2" aria-label="Waiting invites">
          <h2 className="text-[15px] font-semibold">{`Waiting invites · ${waiting.length}`}</h2>
          <ul className="text-sm">
            {waiting.map((i) => (
              <li key={i.id} className="flex flex-col gap-2 border-b border-border py-2 sm:min-h-[50px] sm:flex-row sm:flex-wrap sm:items-center sm:gap-4 sm:py-1">
                <span className="min-w-0 sm:flex-1">
                  <span className="break-all font-medium">{i.email}</span>
                  <span className="text-muted"> · {ROLE[i.role as keyof typeof ROLE] ?? i.role} · ends {day(i.expires_at)}</span>
                </span>
                <CopyLink id={i.id} email={i.email}>
                  <Button variant="ghost" dense aria-label={`Cancel invite for ${i.email}`} busy={cancel.isPending} onClick={() => cancel.mutate(i.id)}>
                    Cancel
                  </Button>
                </CopyLink>
              </li>
            ))}
          </ul>
        </section>
      )}
      {isOwner && gone.length > 0 && (
        <section className="space-y-2" aria-label="Removed">
          <h2 className="text-[15px] font-semibold text-muted">{`Removed · ${gone.length}`}</h2>
          <ul className="text-sm">
            {gone.map((m) => (
              <li key={m.id} className={`${grid} border-b border-border py-2 sm:min-h-[50px] sm:py-0`}>
                <span className="flex min-w-0 items-center gap-2 text-muted">
                  <Avatar name={m.name} faded />
                  <span className="truncate font-medium">{m.name}</span>
                </span>
                <span className="min-w-0 truncate text-muted">{m.email}</span>
                <span className="text-muted">{ROLE[m.role as keyof typeof ROLE] ?? m.role}</span>
                <span className="text-muted">removed</span>
                <span>
                  <Button variant="secondary" dense aria-label={`Restore ${m.name}`} onClick={() => void back(m, `${m.name} is back on the team.`)} className="w-full sm:w-auto">
                    Restore
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      </div>
      {inviting && (
        <InvitePanel
          onClose={() => setInviting(false)}
          onDone={(i) => {
            setFresh(i);
            setInviting(false);
            void refresh();
          }}
        />
      )}
      {changing && (
        <Dialog
          title={changing.to === "owner" ? `Make ${changing.name} an owner?` : `Make ${changing.name} an editor?`}
          cancelLabel={changing.to === "owner" ? "Keep as editor" : "Keep as owner"}
          actionLabel={changing.to === "owner" ? "Make owner" : "Make editor"}
          busy={change.isPending}
          onCancel={() => setChanging(null)}
          onConfirm={() => change.mutate(changing)}
        >
          {changing.to === "owner" ? "Owners see dollars, approve spending, and manage the team." : `${changing.name} stops seeing dollars and can't manage the team.`}
          {change.isError && <p role="alert" className={`mt-2 ${errorClass}`}>{change.error.message}</p>}
        </Dialog>
      )}
      {removing && (
        <Dialog title={`Remove ${removing.name} from the team?`} cancelLabel="Keep them" actionLabel="Remove" danger busy={remove.isPending} onCancel={() => setRemoving(null)} onConfirm={() => remove.mutate(removing)}>
          Their videos stay.
        </Dialog>
      )}
    </main>
  );
}

/** A waiting invite's link can't be shown again (only a hash is kept), so Copy link asks for a fresh one: the old link stops working. */
function CopyLink({ id, email, children }: { id: number; email: string; children?: ReactNode }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const [byHand, setByHand] = useState<string | null>(null); // the link, shown to copy by hand when the clipboard says no
  const fresh = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invites/{invite_id}/link", { params: { path: { invite_id: id } } });
      if (!data) throw new Error(errorText(error));
      return `${location.origin}/invite/${data.token}`;
    },
    onSuccess: async (link) => {
      try {
        await navigator.clipboard.writeText(link);
        setByHand(null);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast("Link copied. The old link no longer works.");
      } catch {
        setByHand(link);
        toast("Couldn't copy the link. It's below, to copy by hand.", undefined, "error");
      }
    },
    onError: (e) => toast(e.message, undefined, "error"),
  });
  return (
    <>
      <span className="flex gap-2 [&>*]:flex-1 sm:[&>*]:flex-none">
        <Button variant="secondary" dense className="whitespace-nowrap" aria-label={`Copy a new link for ${email}`} busy={fresh.isPending} onClick={() => fresh.mutate()}>
          {copied ? "Copied" : "Copy a new link"}
        </Button>
        {children}
      </span>
      {byHand && (
        <span className="basis-full">
          <Field label={`Invite link for ${email}`} readOnly value={byHand} onFocus={(e) => e.currentTarget.select()} />
        </span>
      )}
    </>
  );
}

/** The link just made, at the top of the page (v5 D_Team): copy it and send it. It works once and ends in 7 days. */
function FreshLink({ invite }: { invite: NewInvite }) {
  const [copied, setCopied] = useState(false);
  const link = `${location.origin}/invite/${invite.token}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the link is selectable in the box */
    }
  };
  return (
    <section aria-label="Invite link" className="space-y-2.5 rounded-lg border border-border bg-surface px-4 py-3.5">
      <h2 className="text-sm font-medium">
        Invite link for {invite.role === "owner" ? "an owner" : "an editor"} <span className="font-normal text-muted">· {invite.email}</span>
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="invite-link" className="sr-only">Invite link</label>
        <input id="invite-link" readOnly value={link} onFocus={(e) => e.currentTarget.select()} className="min-h-control w-full min-w-0 rounded-md border border-border-strong bg-bg px-2.5 text-sm sm:w-[360px] lg:min-h-control-dense" />
        <Button variant="secondary" dense onClick={copy} className="w-full sm:w-auto">
          {copied ? "Copied" : "Copy link"}
        </Button>
        <span className="text-xs text-muted">Works once · ends in 7 days</span>
      </div>
    </section>
  );
}

/** v5 D_Team's "Invite link for an editor" (#1247): one standing link, used once, ending in 7 days. Its address can only be
 *  shown right after it's made (only a hash is kept); later the card says it's out, with New link and Stop link. */
function EditorLink() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [made, setMade] = useState<{ url: string; expires_at: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [stopping, setStopping] = useState(false);
  const link = useQuery({ queryKey: ["team", "invite-link"], queryFn: async () => (await api.GET("/team/invite-link")).data ?? null });
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invite-link");
      if (!data) throw new Error(errorText(error));
      return { url: `${location.origin}/invite/${data.token}`, expires_at: data.expires_at };
    },
    onSuccess: async (m) => {
      setMade(m);
      setCopied(false);
      await queryClient.invalidateQueries({ queryKey: ["team", "invite-link"] });
    },
  });
  const stop = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.DELETE("/team/invite-link");
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      setMade(null);
      setStopping(false);
      await queryClient.invalidateQueries({ queryKey: ["team", "invite-link"] });
      toast("The invite link stopped working.");
    },
  });
  const copy = async () => {
    if (!made) return;
    try {
      await navigator.clipboard.writeText(made.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the link is selectable in the box */
    }
  };
  const out = link.data;
  return (
    <section aria-label="Invite link for an editor" className="space-y-2.5 rounded-lg border border-border bg-surface px-4 py-3.5">
      <h2 className="text-sm font-medium">Invite link for an editor</h2>
      {made ? (
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="editor-link" className="sr-only">Invite link</label>
          <input id="editor-link" readOnly value={made.url} onFocus={(e) => e.currentTarget.select()} className="min-h-control w-full min-w-0 rounded-md border border-border-strong bg-bg px-2.5 text-sm sm:w-[360px] lg:min-h-control-dense" />
          <Button variant="secondary" dense onClick={() => void copy()} className="w-full sm:w-auto">
            {copied ? "Copied" : "Copy link"}
          </Button>
          <span className="text-xs text-muted">Works once · ends in 7 days</span>
          <Button variant="secondary" dense busy={make.isPending} onClick={() => make.mutate()}>New link</Button>
          <Button variant="ghost" dense onClick={() => setStopping(true)}>Stop link</Button>
        </div>
      ) : out ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">Link made · ends {day(out.expires_at)}. Its address shows only when it's made.</span>
          <Button variant="secondary" dense busy={make.isPending} onClick={() => make.mutate()}>New link</Button>
          <Button variant="ghost" dense onClick={() => setStopping(true)}>Stop link</Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">Anyone with the link joins as an editor. It works once and ends in 7 days.</span>
          <Button variant="secondary" dense busy={make.isPending} disabled={link.isPending} onClick={() => make.mutate()}>Make link</Button>
        </div>
      )}
      {made && <p className="text-xs text-muted">A new link stops the old one.</p>}
      {make.isError && <p role="alert" className={errorClass}>{make.error.message}</p>}
      {stopping && (
        <Dialog title="Stop the invite link?" cancelLabel="Keep it" actionLabel="Stop link" danger busy={stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => stop.mutate()}>
          No one can join with it after this. You can make a new link at any time.
          {stop.isError && <p role="alert" className={`mt-2 ${errorClass}`}>{stop.error.message}</p>}
        </Dialog>
      )}
    </section>
  );
}

/** Email and role. The link then shows at the top of Team. */
function InvitePanel({ onClose, onDone }: { onClose: () => void; onDone: (invite: NewInvite) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "owner">("editor");
  const invite = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invites", { body: { email, role } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: onDone,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    invite.mutate();
  };
  return (
    <Panel title="Invite someone" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email to invite" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Select label="Role" value={role} onChange={(e) => setRole(e.target.value as "editor" | "owner")}>
          <option value="editor">Editor</option>
          <option value="owner">Owner</option>
        </Select>
        {invite.isError && <p role="alert" className={errorClass}>{invite.error.message}</p>}
        <Button type="submit" busy={invite.isPending} className="w-full">
          Create invite link
        </Button>
      </form>
    </Panel>
  );
}
