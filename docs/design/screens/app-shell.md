# App shell, brand switcher, team

Purpose: every screen sits inside a brand. You always see which brand, and switching is one click.

## Desktop (1440)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ [● fomo ▾]                    ⌕ Search fomo…            [◐] [RP ▾]       │ top bar 56
├▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬┤ 3px --brand stripe
│ Projects        │  Projects                                  [+ New video] │
│ Quick clip      │  ┌────────┐ ┌────────┐ ┌────────┐                       │
│ ─────────       │  │ thumb  │ │ thumb  │ │ thumb  │  cards 3–4 per row   │
│ Library         │  │ Title  │ │ Title  │ │ Title  │                       │
│   Characters    │  │ Script · 62% budget │ │        │                       │
│   Places        │  └────────┘ └────────┘ └────────┘                       │
│   Props         │                                                          │
│ Brand kit       │                                                          │
│ ─────────       │                                                          │
│ Team            │                                                          │
│ Usage  (owner)  │                                                          │
└─────────────────┴──────────────────────────────────────────────────────────┘
  sidebar 232
```
- Active nav item: `accent-soft` background, `accent-text`.
- Theme toggle `◐` cycles System / Light / Dark (stored in localStorage).
- Avatar menu: name, role, Theme, Log out.

## Brand switcher (popover, 280 wide)
```
┌──────────────────────────┐
│ ● fomo                ✓  │  logo 20px or colour dot + name
│ ● Iron Paws              │
│ ──────────────────────── │
│ + New brand   (owner)    │
└──────────────────────────┘
```
Switching keeps you on the same section (Library → Library of the new brand) and puts the brand in the URL: `/b/fomo/library/characters`. Keyboard: `⌘K`/`Ctrl K` opens it.

## Phone (390)
```
┌──────────────────────────────┐
│ [● fomo ▾]          [◐] [RP] │ 56
├▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬┤
│ Projects          [+ New]    │
│ ┌──────────────────────────┐ │ one card per row
│ │ thumb  Title             │ │
│ │        Script · 62%      │ │
│ └──────────────────────────┘ │
├──────────────────────────────┤
│ Projects  Clip  Library  More│ bottom tabs 64, icon + label
└──────────────────────────────┘
```
"More" opens a sheet: Brand kit, Team, Usage (owner), Theme, Log out. Search moves into each page's header.

## Projects list
Cards: thumbnail (latest frame or brand logo on `--surface-2`), title, stage ("Script", "Clips 6/9", "Final cut"), budget % badge (warning ≥ 75, danger > 100). Empty: "No videos for fomo yet." / "Start from a brief or a script." / [New video].

## Team (`/team`)
Table: Name, Email, Role, Joined, ⋯ (owner: Remove). Below: Invites table (Email, Role, Expires, Copy link, Cancel). Owner button "Invite someone" → dialog: Email, Role (Editor / Owner), [Create invite] → shows the link with [Copy link] and "Send this link yourself. It works once and expires on <date>." Editors see the members table only.
Phone: each row becomes a stacked list item; actions in ⋯.
