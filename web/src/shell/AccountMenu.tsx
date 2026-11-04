import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChartColumn, Clapperboard, Settings, UserPlus, type LucideIcon } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Menu, MenuItem } from "../components";
import { applyTheme, getTheme, type Theme } from "../theme";

// Reed's Studio pages: rows in the rail after Needs you; on a phone, in the account menu (Needs you is the top bar's bell).
export const STUDIO: [string, string, LucideIcon][] = [
  ["/production", "In production", Clapperboard],
  ["/usage", "Usage", ChartColumn],
  ["/team", "Team", UserPlus],
  ["/settings", "Settings", Settings],
];

const THEMES: { id: Theme; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "system", label: "System" },
];

export function AccountMenu({ inRail, iconOnly }: { inRail?: boolean; iconOnly?: boolean } = {}) {
  const { data: me } = useMe();
  const signOut = useSignOut();
  const [theme, setTheme] = useState<Theme>(getTheme);
  // An editor's week, as the My credits row shows it: "142 of 200 left" (v5 A_Account).
  const week = useQuery({
    enabled: me?.role === "editor",
    queryKey: ["credits-me"],
    queryFn: async () => (await api.GET("/credits/me")).data ?? null,
  }).data;
  const left = week ? Math.max(0, Math.floor(week.quick_clip_credits_allowed - week.quick_clip_credits_used)) : null;
  const initials = (me?.name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <Menu
      title="Account"
      align={inRail ? "left" : "right"}
      up={inRail}
      trigger={(p) =>
        inRail ? (
          <button type="button" {...p} aria-label="Account menu" className={`flex min-h-control w-full items-center gap-2 rounded-md px-2 hover:bg-surface-2 ${iconOnly ? "justify-center" : ""}`}>
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-3 text-xs font-semibold">{initials}</span>
            {!iconOnly && <span className="min-w-0 flex-1 truncate text-left">{me?.name}</span>}
            {!iconOnly && me && <span className="text-xs text-muted">{me.role === "owner" ? "Owner" : "Editor"}</span>}
          </button>
        ) : (
          <button type="button" {...p} aria-label="Account menu" className="grid size-control place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-text">
            {initials}
          </button>
        )
      }
    >
      {(close) => (
        <>
          <div className="px-3 pb-2 pt-1">
            <div>
              <span className="font-semibold">{me?.name}</span>
              {me && <span className="text-sm text-muted"> · {me.role === "owner" ? "Owner" : "Editor"}</span>}
            </div>
            <div className="text-sm text-muted">{me?.email}</div>
          </div>
          {me?.role === "owner" &&
            !inRail &&
            STUDIO.map(([to, label, Icon]) => (
              <Link key={to} to={to} onClick={close} className="flex min-h-control items-center gap-3 rounded-md px-3 hover:bg-surface-2">
                <Icon size={20} strokeWidth={1.75} aria-hidden />
                {label}
              </Link>
            ))}
          {me?.role === "editor" && (
            <Link to="/usage/mine" onClick={close} className="flex min-h-control items-center gap-3 rounded-md px-3 hover:bg-surface-2">
              <span className="flex-1">My credits</span>
              {week && left !== null && <span className="text-sm tabular-nums text-muted">{Math.floor(left)} of {Math.floor(week.quick_clip_credits_allowed)} left</span>}
            </Link>
          )}
          {/* v5 A_Account: Theme as one segmented control, Dark / Light / System. */}
          <div role="group" aria-label="Theme" className="mt-1 flex items-center gap-3 border-t border-border px-3 pb-1 pt-2">
            <span className="text-sm text-muted">Theme</span>
            <span className="ml-auto inline-flex rounded-md border border-border-strong bg-bg p-0.5">
              {THEMES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={theme === t.id}
                  className={`min-h-control rounded px-2.5 text-sm lg:min-h-control-dense ${theme === t.id ? "bg-surface-3 font-medium text-text ring-1 ring-inset ring-border-strong" : "text-muted hover:text-text"}`}
                  onClick={() => {
                    applyTheme(t.id);
                    setTheme(t.id);
                  }}
                >
                  {t.label}
                </button>
              ))}
            </span>
          </div>
          <div className="mt-1 border-t border-border pt-1">
            <MenuItem onClick={() => signOut.mutate()}>Sign out</MenuItem>
          </div>
        </>
      )}
    </Menu>
  );
}

function useSignOut() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.POST("/auth/logout"),
    onSuccess: () => {
      queryClient.clear(); // nothing from this person stays for the next one
      navigate("/login", { replace: true });
    },
  });
}
