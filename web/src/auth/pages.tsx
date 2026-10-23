import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
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
      footer={
        <p className="text-sm text-neutral-600">
          First time here? <Link className="underline" to="/setup">Set up the studio</Link>
        </p>
      }
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
        <p className="text-sm text-neutral-600">
          Already set up? <Link className="underline" to="/login">Sign in</Link>
        </p>
      }
    />
  );
}

export function InvitePage() {
  const { token = "" } = useParams();
  return (
    <AuthForm
      title="Join the studio"
      submitLabel="Create my account"
      fields={[
        { name: "name", label: "Your name", autoComplete: "name" },
        { name: "password", label: "Choose a password (10 or more characters)", type: "password", autoComplete: "new-password" },
      ]}
      submit={(v) => api.POST("/auth/accept-invite", { body: { token, name: v.name, password: v.password } })}
    />
  );
}
