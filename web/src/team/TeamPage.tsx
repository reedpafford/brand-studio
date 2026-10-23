import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";

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
        <h1 className="mb-3 text-2xl font-semibold">Team</h1>
        <ul className="divide-y divide-neutral-200">
          {members.data?.map((m) => (
            <li key={m.id} className="flex items-center gap-3 py-2">
              <span className="flex-1">
                {m.name} <span className="text-sm text-neutral-600">{m.email} · {m.role}</span>
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
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Invite someone</h2>
          <InviteForm onDone={refresh} />
          {invites.data && invites.data.length > 0 && (
            <ul className="divide-y divide-neutral-200">
              {invites.data.map((i) => (
                <li key={i.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="flex-1">
                    {i.email} · {i.role} · waiting
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
  const invite = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/team/invites", { body: { email, role } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => {
      setEmail("");
      onDone();
    },
  });
  const link = invite.data && `${location.origin}/invite/${invite.data.token}`;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    invite.mutate();
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <label className="flex-1 text-sm">
          <span className="sr-only">Email to invite</span>
          <input
            className="w-full rounded border border-neutral-300 px-3 py-2 text-base"
            type="email"
            required
            placeholder="Email"
            aria-label="Email to invite"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <select
          aria-label="Role"
          className="rounded border border-neutral-300 px-2 py-2"
          value={role}
          onChange={(e) => setRole(e.target.value as "editor" | "owner")}
        >
          <option value="editor">Editor</option>
          <option value="owner">Owner</option>
        </select>
        <button className="rounded bg-neutral-900 px-3 py-2 text-white disabled:opacity-50" disabled={invite.isPending}>
          Create invite link
        </button>
      </div>
      {invite.isError && (
        <p role="alert" className="text-sm text-red-700">
          {invite.error.message}
        </p>
      )}
      {link && (
        <p className="text-sm">
          Send this link to {invite.data.email}. It is shown only once:
          <input readOnly aria-label="Invite link" className="mt-1 w-full rounded bg-neutral-100 px-2 py-1" value={link} onFocus={(e) => e.target.select()} />
        </p>
      )}
    </form>
  );
}
