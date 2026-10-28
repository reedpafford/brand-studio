import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useEffect, useState } from "react";
import { Link2Off } from "lucide-react";
import { Button, Card, Skeleton } from "../components";
import { linkText } from "../ui";
import { AuthForm, AuthShell } from "./AuthForm";

export function LoginPage() {
  return (
    <AuthForm
      title="Sign in"
      submitLabel="Sign in"
      busyLabel="Signing in…"
      fields={[
        { name: "email", label: "Email", type: "email", autoComplete: "email" },
        { name: "password", label: "Password", type: "password", autoComplete: "current-password" },
      ]}
      submit={(v) => api.POST("/auth/login", { body: { email: v.email, password: v.password } })}
      footer={<p className="text-sm text-muted">Forgot your password? Ask the owner.</p>}
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
        { name: "workspace_name", label: "Studio name", hint: "What your team sees when they're invited, e.g. Northside Studio." },
        { name: "name", label: "Your name", autoComplete: "name" },
        { name: "email", label: "Email", type: "email", autoComplete: "email" },
        { name: "password", label: "Password (10 or more characters)", type: "password", autoComplete: "new-password", minLength: 10 },
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
          Already set up? <Link className={`${linkText} inline-flex min-h-control items-center`} to="/login">Sign in</Link>
        </p>
      }
    />
  );
}

class InviteGone extends Error {}

/** A stored name like "owner-reed" is a slug, not a name. The owner's own settings say "{owner}'s studio"; anyone else is told "your team's studio" (editors never see the owner's name). */
export function studioName(stored: string, owner?: string) {
  const slug = !/\s/.test(stored.trim()) && stored.includes("-");
  return !slug ? stored : owner ? `${owner}'s studio` : "your team's studio";
}

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
  if (invite.isPending) return <Checking />;
  if (invite.isError && !(invite.error instanceof InviteGone))
    return (
      <AuthShell>
        <Card className="space-y-3 p-5 sm:p-6">
          <h1 className="type-page">Could not check your invite</h1>
          <p role="alert">Check your connection and try again.</p>
          <Button busy={invite.isFetching} onClick={() => invite.refetch()} className="w-full">
            Try again
          </Button>
        </Card>
      </AuthShell>
    );
  if (invite.isError)
    return (
      <AuthShell>
        <Card className="space-y-3 p-5 text-center sm:p-6">
          <Link2Off size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-muted" />
          <h1 className="type-page">Invite not valid</h1>
          <p role="alert">This invite link is not valid any more.</p>
          <p className="text-sm text-muted">Ask whoever invited you to send a new link.</p>
          <p>
            Already have an account?{" "}
            <Link className={`${linkText} inline-flex min-h-control items-center`} to="/login">
              Sign in
            </Link>
          </p>
        </Card>
      </AuthShell>
    );
  const i = invite.data;
  const studio = studioName(i.workspace_name);
  return (
    <AuthForm
      title={`Join ${studio}`}
      intro={
        <p className="text-sm text-muted">
          {i.invited_by_name ? `${i.invited_by_name} invited you` : "You were invited"} to {studio} as {i.role === "owner" ? "an owner" : "an editor"}. Your email is {i.email}.
        </p>
      }
      submitLabel="Create my account"
      fields={[
        { name: "name", label: "Your name", autoComplete: "name" },
        { name: "password", label: "Choose a password (10 or more characters)", type: "password", autoComplete: "new-password", minLength: 10 },
      ]}
      submit={(v) => api.POST("/auth/accept-invite", { body: { token, name: v.name, password: v.password } })}
      welcome={(v) => `Welcome to ${studio}, ${v.name}.`}
    />
  );
}

/** A skeleton card while the link is checked; after a second it says so. */
function Checking() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 1000);
    return () => clearTimeout(t);
  }, []);
  return (
    <AuthShell>
      <Card className="space-y-4 p-5 sm:p-6">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-11" />
        <Skeleton className="h-11" />
        {slow && (
          <p className="text-sm text-muted" role="status">
            Checking your invite…
          </p>
        )}
      </Card>
    </AuthShell>
  );
}
