# Login, first-time setup, accept invite

Purpose: get a team member in with the fewest fields. No sign-up page: people join by invite.
API: `POST /auth/login`, `POST /auth/setup`, `POST /auth/accept-invite`, `GET /auth/me`.

## Desktop (1440)
```
┌──────────────────────────────────────────────────────────────┐
│                         (bg)                                  │
│                ┌──────────────────────────┐                   │
│                │ ▣ Brand Studio            │  card 400 wide   │
│                │                           │                   │
│                │ Log in                    │  text-xl          │
│                │ Email      [____________] │                   │
│                │ Password   [________] 👁  │  show/hide toggle │
│                │ [        Log in         ] │  primary, full    │
│                │ Forgot password? Ask Reed.│  text-sm muted    │
│                └──────────────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```
Card centred vertically, no imagery, no marketing.

## Phone (390)
Same card, full width minus 16px gutters, top-aligned at 25% height. Inputs 44px tall, 16px text.

## Variants
- **Setup** (`/setup`, only while no owner exists): title "Set up Brand Studio". Fields: Your name, Email, Password (helper "At least 10 characters"), Setup code (helper "From the server's settings"). Button "Create workspace". After: lands on Projects with fomo and Iron Paws already there.
- **Accept invite** (`/invite/:token`): title "Join Reed's team". Line: "You were invited as an editor." Email shown read-only. Fields: Your name, Password. Button "Join". Expired/used link: "This invite has expired or was already used. Ask the person who invited you for a new link." No form.

## States and copy
- Wrong details: banner (danger) inside the card "Email or password is wrong." Do not say which.
- Throttled: "Too many tries. Wait a minute and try again." Button disabled with that reason below it.
- Busy: button "Logging in…" with spinner, inputs disabled.
- After login: return to the page they came from, else Projects of the last brand used.
