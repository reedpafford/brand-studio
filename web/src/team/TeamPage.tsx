import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy } from "lucide-react";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, Field, Panel, Select, Skeleton } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";

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
      return m.name;
    },
    onSuccess: async (name) => {
      setRemoving(null);
      await refresh();
      toast(`${name} removed.`);
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
                  </span>
                  <Badge>{ROLE[m.role as keyof typeof ROLE] ?? m.role}</Badge>
                  {isOwner && m.id !== me?.id && (
                    <Button variant="ghost" dense aria-label={`Remove ${m.name}`} onClick={() => setRemoving({ id: m.id, name: m.name })}>
                      Remove
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {isOwner && onlyMe && <p className="text-sm text-muted">Invite your editors so they can make videos.</p>}
      </section>
      {isOwner && invites.data && invites.data.length > 0 && (
        <section className="space-y-3" aria-label="Waiting invites">
          <h2 className="type-section">Waiting invites</h2>
          <Card className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {invites.data.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-3 p-3 text-sm sm:px-5">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{i.email}</span>
                    <span className="block text-muted">{ROLE[i.role as keyof typeof ROLE] ?? i.role} · expires {day(i.expires_at)}</span>
                  </span>
                  <Button variant="ghost" dense aria-label={`Cancel invite for ${i.email}`} busy={cancel.isPending} onClick={() => cancel.mutate(i.id)}>
                    Cancel
                  </Button>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
      {inviting && <InvitePanel onClose={() => setInviting(false)} onDone={refresh} />}
      {removing && (
        <Dialog title={`Remove ${removing.name} from the team?`} cancelLabel="Keep them" actionLabel="Remove" danger busy={remove.isPending} onCancel={() => setRemoving(null)} onConfirm={() => remove.mutate(removing)}>
          Their videos stay.
        </Dialog>
      )}
    </main>
  );
}

/** Email and role, then the link to send. The link is shown once. */
function InvitePanel({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "owner">("editor");
  const [copied, setCopied] = useState(false);
  const invite = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invites", { body: { email, role } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      setCopied(false);
      onDone();
      toast(`Invite link made. Copy it and send it to ${data.email}.`);
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
