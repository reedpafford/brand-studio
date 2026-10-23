import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, pageTitle } from "../ui";

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function TeamPage() {
  const { data: me } = useMe();
  const isOwner = me?.role === "owner";
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["team"] });

  const members = useQuery({
    queryKey: ["team", "members"],
    queryFn: async () => (await api.GET("/team/members")).data ?? [],
  });
  const invites = useQuery({
    queryKey: ["team", "invites"],
    enabled: isOwner,
    queryFn: async () => (await api.GET("/team/invites")).data ?? [],
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.DELETE("/team/members/{member_id}", { params: { path: { member_id: id } } }),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: (id: number) => api.DELETE("/team/invites/{invite_id}", { params: { path: { invite_id: id } } }),
    onSuccess: refresh,
  });

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <section>
        <h1 className={`${pageTitle} mb-3`}>Team</h1>
        <ul className="divide-y divide-border">
          {members.data?.map((m) => (
            <li key={m.id} className="flex items-center gap-3 py-2">
              <span className="flex-1">
                {m.name} <span className="text-sm text-muted">{m.email} · {m.role}</span>
              </span>
              {isOwner && m.id !== me?.id && (
                <button
                  className="text-sm underline"
                  aria-label={`Remove ${m.name}`}
                  onClick={() => window.confirm(`Remove ${m.name} from the team?`) && remove.mutate(m.id)}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
      {isOwner && (
        <section className={`${card} space-y-4`}>
          <h2 className="text-[length:var(--text-md)] font-semibold">Invite someone</h2>
          <InviteForm onDone={refresh} />
          {invites.data && invites.data.length > 0 && (
            <ul className="divide-y divide-border">
              {invites.data.map((i) => (
                <li key={i.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="flex-1">
                    {i.email} · {i.role} · waiting, expires {day(i.expires_at)}
                  </span>
                  <button className="underline" aria-label={`Cancel invite for ${i.email}`} onClick={() => cancel.mutate(i.id)}>
                    Cancel
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}

function InviteForm({ onDone }: { onDone: () => void }) {
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
      setEmail("");
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
    } catch {
      /* clipboard blocked: the link is selectable below */
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
        <input
          className={`${input} min-h-11 sm:min-h-9`}
          type="email"
          required
          placeholder="Email"
          aria-label="Email to invite"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <div className="grid grid-cols-[auto_1fr] gap-2 sm:contents">
          <select
            aria-label="Role"
            className={`${input} min-h-11 w-auto sm:min-h-9`}
            value={role}
            onChange={(e) => setRole(e.target.value as "editor" | "owner")}
          >
            <option value="editor">Editor</option>
            <option value="owner">Owner</option>
          </select>
          <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={invite.isPending}>
            Create invite link
          </button>
        </div>
      </div>
      {invite.isError && (
        <p role="alert" className={errorClass}>
          {invite.error.message}
        </p>
      )}
      {link && (
        <div className="space-y-2 text-sm">
          <p>
            Send this link to {invite.data.email}. Works once. Expires {day(invite.data.expires_at)}.
          </p>
          <div className="flex gap-2">
            <input readOnly aria-label="Invite link" className={`${input} min-w-0 bg-surface-2`} value={link} onFocus={(e) => e.target.select()} />
            <button type="button" className={`${btnSecondary} shrink-0`} onClick={copy}>
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
        </div>
      )}
    </form>
  );
}
