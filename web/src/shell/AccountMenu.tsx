import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChartColumn, Check, Clapperboard, Coins, LogOut, Settings, UserPlus, type LucideIcon } from "lucide-react";
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
  { id: "system", label: "Match my device" },
];

export function AccountMenu({ inRail, iconOnly }: { inRail?: boolean; iconOnly?: boolean } = {}) {
  const { data: me } = useMe();
  const signOut = useSignOut();
  const [theme, setTheme] = useState<Theme>(getTheme);
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
            <div className="font-semibold">{me?.name}</div>
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
              <Coins size={20} strokeWidth={1.75} aria-hidden />
              My credits
            </Link>
          )}
          <div role="group" aria-label="Theme" className="mt-1 border-t border-border pt-1">
            <p className="px-3 pt-2 text-xs font-bold uppercase tracking-[0.12em] text-muted">Theme</p>
            {THEMES.map((t) => (
              <MenuItem
                key={t.id}
                checked={theme === t.id}
                onClick={() => {
                  applyTheme(t.id);
                  setTheme(t.id);
                }}
              >
                <span className="flex-1">{t.label}</span>
                {theme === t.id && <Check size={20} strokeWidth={1.75} aria-hidden />}
              </MenuItem>
            ))}
          </div>
          <div className="mt-1 border-t border-border pt-1">
            <MenuItem onClick={() => signOut.mutate()}>
              <LogOut size={20} strokeWidth={1.75} aria-hidden />
              Sign out
            </MenuItem>
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
