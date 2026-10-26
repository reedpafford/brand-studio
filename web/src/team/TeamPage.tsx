import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Ellipsis, UserCog, UserMinus } from "lucide-react";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, Field, Menu, MenuItem, Panel, Select, Skeleton } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { CreditLimits } from "./CreditLimits";
import { restoreMember, setRole, useRemovedMembers } from "./memberActions";

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const ROLE = { owner: "Owner", editor: "Editor" } as const;

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
  const [showRemoved, setShowRemoved] = useState(false);
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
  const invite = isOwner && (
    <Button onClick={() => setInviting(true)}>Invite someone</Button>
  );
  const onlyMe = members.data?.length === 1;

  return (
    <main className="mx-auto max-w-[720px] space-y-6 p-4 sm:p-6">
      <div className="flex items-end justify-between gap-3">
        <h1 className="type-page">Team</h1>
        {invite && rail && invite}
      </div>
      {invite && !rail && <ActionBar phone>{invite}</ActionBar>}
      {(members.isError || remove.isError) && (
        <Banner title={remove.isError ? "Couldn't remove that person." : "Couldn't load the team."} action={members.isError ? <Button variant="secondary" onClick={() => void members.refetch()}>Try again</Button> : undefined}>
          {remove.isError ? "Try again." : "Check your connection."}
        </Banner>
      )}
      {isOwner && <CreditLimits />}
      <section className="space-y-3" aria-label="People">
        <h2 className="type-section">People</h2>
        {members.isPending && (
          <div className="space-y-2" aria-label="Loading">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        )}
        {members.data && (
          <Card className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {members.data.map((m) => (
                <li key={m.id} className="flex items-center gap-3 p-3 sm:px-5">
                  <span aria-hidden className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft font-display font-bold text-accent-text">
                    {m.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{m.name}</span>
                    <span className="block truncate text-sm text-muted">{m.email}</span>
                    <span className="mt-1 inline-flex sm:hidden">
                      <Badge>{ROLE[m.role as keyof typeof ROLE] ?? m.role}</Badge>
                    </span>
                  </span>
                  <span className="hidden sm:inline-flex">
                    <Badge>{ROLE[m.role as keyof typeof ROLE] ?? m.role}</Badge>
                  </span>
                  {isOwner && m.id !== me?.id && (
                    <Menu
                      title={`More for ${m.name}`}
                      align="right"
                      trigger={(t) => (
                        <button type="button" {...t} aria-label={`More for ${m.name}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
                          <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                        </button>
                      )}
                    >
                      {(close) => (
                        <>
                          <MenuItem
                            onClick={() => {
                              close();
                              setChanging({ id: m.id, name: m.name, to: m.role === "owner" ? "editor" : "owner" });
                            }}
                          >
                            <UserCog size={20} strokeWidth={1.75} aria-hidden />
                            {m.role === "owner" ? "Make editor" : "Make owner"}
                          </MenuItem>
                          <MenuItem
                            danger
                            onClick={() => {
                              close();
                              setRemoving({ id: m.id, name: m.name });
                            }}
                          >
                            <UserMinus size={20} strokeWidth={1.75} aria-hidden />
                            Remove
                          </MenuItem>
                        </>
                      )}
                    </Menu>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {isOwner && onlyMe && <p className="text-sm text-muted">Invite your editors so they can make videos.</p>}
        {isOwner && (removed.data?.length ?? 0) > 0 && (
          <div className="space-y-2">
            <Button variant="ghost" aria-expanded={showRemoved} onClick={() => setShowRemoved(!showRemoved)}>
              {showRemoved ? "Hide removed" : `Show removed (${removed.data?.length})`}
            </Button>
            {showRemoved && (
              <Card className="p-0 sm:p-0">
                <ul className="divide-y divide-border text-muted">
                  {removed.data?.map((m) => (
                    <li key={m.id} className="flex items-center gap-3 p-3 sm:px-5">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-semibold">{m.name}</span>
                        <span className="block truncate text-sm">{m.email} · Removed</span>
                      </span>
                      <Button variant="secondary" dense aria-label={`Restore ${m.name}`} onClick={() => void back(m, `${m.name} is back on the team.`)}>
                        Restore
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
      </section>
      {isOwner && invites.data && invites.data.length > 0 && (
        <section className="space-y-3" aria-label="Waiting invites">
          <h2 className="type-section">Waiting invites</h2>
          <Card className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {invites.data.map((i) => (
                <li key={i.id} className="flex flex-col gap-3 p-3 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:px-5">
                  <span className="min-w-0 sm:flex-1">
                    <span className="block break-all font-medium">{i.email}</span>
                    <span className="block text-muted">{ROLE[i.role as keyof typeof ROLE] ?? i.role} · expires {day(i.expires_at)}</span>
                  </span>
                  <CopyLink id={i.id} email={i.email}>
                    <Button variant="ghost" dense aria-label={`Cancel invite for ${i.email}`} busy={cancel.isPending} onClick={() => cancel.mutate(i.id)}>
                      Cancel
                    </Button>
                  </CopyLink>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
      {inviting && <InvitePanel onClose={() => setInviting(false)} onDone={refresh} />}
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
        <Button variant="secondary" dense className="whitespace-nowrap" icon={copied ? Check : Copy} aria-label={`Copy a new link for ${email}`} busy={fresh.isPending} onClick={() => fresh.mutate()}>
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

/** Email and role, then the link to send. The link is shown once. */
function InvitePanel({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "owner">("editor");
  const [copied, setCopied] = useState(false);
  const invite = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invites", { body: { email, role } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => {
      setCopied(false);
      onDone();
    },
  });
  const link = invite.data && `${location.origin}/invite/${invite.data.token}`;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    invite.mutate();
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link!);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the link is selectable in the box */
    }
  };
  return (
    <Panel title="Invite someone" onClose={onClose}>
      {link ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">Send this link to {invite.data.email}. It works once and expires in 7 days.</p>
          <Field label="Invite link" readOnly value={link} onFocus={(e) => e.target.select()} />
          <Button variant="secondary" icon={copied ? Check : Copy} className="w-full" onClick={copy}>
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button variant="ghost" className="w-full" onClick={onClose}>
            Done
          </Button>
        </div>
      ) : (
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
      )}
    </Panel>
  );
}
