import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { btnPrimary, card, linkText } from "../ui";
import { AuthForm } from "./AuthForm";

export function LoginPage() {
  return (
    <AuthForm
      title="Sign in"
      submitLabel="Sign in"
      fields={[
        { name: "email", label: "Email", type: "email", autoComplete: "username" },
        { name: "password", label: "Password", type: "password", autoComplete: "current-password" },
      ]}
      submit={(v) => api.POST("/auth/login", { body: { email: v.email, password: v.password } })}
    />
  );
}

export function SetupPage() {
  return (
    <AuthForm
      title="Set up the studio"
      submitLabel="Create owner account"
      fields={[
        { name: "setup_token", label: "Setup code (from your server settings)", type: "password" },
        { name: "workspace_name", label: "Studio name" },
        { name: "name", label: "Your name", autoComplete: "name" },
        { name: "email", label: "Email", type: "email", autoComplete: "username" },
        { name: "password", label: "Password (10 or more characters)", type: "password", autoComplete: "new-password" },
      ]}
      submit={(v) =>
        api.POST("/auth/setup", {
          body: {
            setup_token: v.setup_token,
            workspace_name: v.workspace_name,
            name: v.name,
            email: v.email,
            password: v.password,
          },
        })
      }
      footer={
        <p className="text-sm text-muted">
          Already set up? <Link className={linkText} to="/login">Sign in</Link>
        </p>
      }
    />
  );
}

class InviteGone extends Error {}

export function InvitePage() {
  const { token = "" } = useParams();
  // Who invited you, to which studio. The token goes in the body, never the address, so it stays out of logs.
  const invite = useQuery({
    queryKey: ["invite", token],
    retry: false,
    queryFn: async () => {
      // Only a 404 means the link is dead; a dropped connection or a server error is just "try again".
      const { data, response } = await api.POST("/auth/invite", { body: { token } }).catch(() => ({ data: undefined, response: undefined }));
      if (response?.status === 404) throw new InviteGone();
      if (!data) throw new Error("Could not check this invite. Check your connection and try again.");
      return data;
    },
  });
  if (invite.isPending) return <p className="p-6 text-muted">Checking your invite…</p>;
  if (invite.isError && !(invite.error instanceof InviteGone))
    return (
      <main className="mx-auto flex min-h-screen max-w-[432px] flex-col justify-start gap-4 p-4 pt-[20vh] sm:justify-center sm:pt-4">
        <div className={`${card} space-y-3`}>
          <h1 className="text-xl font-semibold">Could not check your invite</h1>
          <p role="alert">{invite.error.message}</p>
          <button className={`${btnPrimary} min-h-11`} disabled={invite.isFetching} onClick={() => invite.refetch()}>
            Try again
          </button>
        </div>
      </main>
    );
  if (invite.isError)
    return (
      <main className="mx-auto flex min-h-screen max-w-[432px] flex-col justify-start gap-4 p-4 pt-[20vh] sm:justify-center sm:pt-4">
        <div className={`${card} space-y-2`}>
          <h1 className="text-xl font-semibold">Invite not valid</h1>
          <p role="alert">This invite link is not valid any more.</p>
          <p className="text-muted">Ask whoever invited you to send a new link.</p>
          <p>
            Already have an account?{" "}
            <Link className={`${linkText} inline-flex min-h-11 items-center sm:min-h-0`} to="/login">
              Sign in
            </Link>
          </p>
        </div>
      </main>
    );
  const i = invite.data;
  return (
    <AuthForm
      title={`Join ${i.workspace_name}`}
      intro={
        <p className="text-sm text-muted">
          {i.invited_by_name ? `${i.invited_by_name} invited you` : "You were invited"} to {i.workspace_name} as {i.role === "owner" ? "an owner" : "an editor"}. Your email is {i.email}.
        </p>
      }
      submitLabel="Create my account"
      fields={[
        { name: "name", label: "Your name", autoComplete: "name" },
        { name: "password", label: "Choose a password (10 or more characters)", type: "password", autoComplete: "new-password" },
      ]}
      submit={(v) => api.POST("/auth/accept-invite", { body: { token, name: v.name, password: v.password } })}
    />
  );
}
