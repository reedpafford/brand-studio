import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChartColumn, ChevronRight, Clapperboard, Settings, UserPlus, UserRound, type LucideIcon } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Menu, MenuItem } from "../components";

// Reed's Studio pages: rows in the rail after Needs you; on a phone, rows in the More tab (S-gaps-04 R3).
export const STUDIO: [string, string, LucideIcon][] = [
  ["/production", "In production", Clapperboard],
  ["/usage", "Usage", ChartColumn],
  ["/team", "Team", UserPlus],
  ["/settings", "Settings", Settings],
];

export function AccountMenu({ inRail, iconOnly, row }: { inRail?: boolean; iconOnly?: boolean; /** A phone's More list (S-gaps-04 R3): "Your account" */ row?: boolean } = {}) {
  const { data: me } = useMe();
  const signOut = useSignOut();
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
        row ? (
          <button type="button" {...p} className="flex min-h-12 w-full items-center gap-3 border-b border-border px-4 text-left text-md">
            <UserRound size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
            <span className="flex-1">Your account</span>
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
          </button>
        ) : inRail ? (
          <button type="button" {...p} aria-label="Account menu" className={`flex min-h-control w-full items-center gap-2 rounded-md px-2 hover:bg-surface-2 ${iconOnly ? "justify-center" : ""}`}>
            <span className={`grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${me?.role === "editor" ? "bg-success-soft text-success" : "bg-accent-soft text-accent-text"}`}>{initials}</span>
            {!iconOnly && <span className="min-w-0 flex-1 truncate text-left">{me?.name}</span>}
            {!iconOnly && <Settings size={14} strokeWidth={1.75} aria-hidden className="text-faint" />}
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
            !row &&
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
          <div className="mt-1 border-t border-border pt-1">
            <MenuItem onClick={() => signOut.mutate()}>Sign out</MenuItem>
          </div>
        </>
      )}
    </Menu>
  );
}

export function useSignOut() {
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
