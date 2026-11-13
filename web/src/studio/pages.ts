import { Clapperboard, Library, Plus, Wallet } from "lucide-react";

/** The studio's four pages: the rail's word for each, and its title. */
export const PAGES = [
  { page: "", label: "Create", title: "New video", icon: Plus },
  { page: "videos", label: "Videos", title: "Videos", icon: Clapperboard },
  { page: "library", label: "Library", title: "Library", icon: Library },
  { page: "spend", label: "Spend", title: "Spend", icon: Wallet },
] as const;
