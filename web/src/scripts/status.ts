import { useEffect, useState } from "react";
import { Check, CircleAlert, Clock, Pencil } from "lucide-react";
import type { Tone } from "../components";
import { serverTime } from "../time";

/** A version someone has started and not finished: its words are being made into a video. */
export const beingMade = (status: string) => status === "in_production" || status === "clips_ready";

/** A version's status in words, with a tone as the second signal. Never an internal word. `short` is the lists' word. */
export const STATUS: Record<string, { label: string; short: string; tone: Tone; icon?: typeof Check }> = {
  draft: { label: "Writing", short: "Writing", tone: "neutral", icon: Pencil },
  // v5 C_Scripts: Ready to make is amber (it waits on someone), Making is indigo, Writing is a hollow ring.
  approved: { label: "Ready to make", short: "Ready", tone: "warning" },
  in_production: { label: "In production", short: "Making", tone: "accent", icon: Clock },
  clips_ready: { label: "In production", short: "Making", tone: "accent", icon: Clock },
  done: { label: "Finished", short: "Finished", tone: "success", icon: Check },
  failed: { label: "Didn't finish", short: "Didn't finish", tone: "danger", icon: CircleAlert },
};
export const statusOf = (s: string) => STATUS[s] ?? { label: s, short: s, tone: "neutral" as Tone };

const LETTER = ["A", "B", "C"];
export const letterOf = (slot: number) => LETTER[slot] ?? String(slot + 1);

/** "just now", "5 min ago", "3 h ago", "yesterday", "2 days ago", then the date. */
export function age(iso: string, now = Date.now()) {
  const mins = Math.max(0, Math.floor((now - serverTime(iso).getTime()) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function useDebounced<T>(value: T, ms = 300) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}
