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
│                │ Sign in                   │  text-xl          │
│                │ Email      [____________] │                   │
│                │ Password   [________] 👁  │  show/hide toggle │
│                │ [        Sign in        ] │  primary, full    │
│                │ Forgot password? Ask Reed.│  text-sm muted    │
│                └──────────────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```
Card centred vertically, no imagery, no marketing.

## Phone (390)
Same card, full width minus 16px gutters, top-aligned at 25% height. Inputs 44px tall, 16px text.

## Variants
- **Setup** (`/setup`, only while no owner exists): title "Set up Brand Studio". Fields: Your name, Email, Password (helper "At least 10 characters"), Setup code (helper "From the server's settings"). Button "Create workspace". After: lands on Projects with fomo and Iron Paws already there.
- **Accept invite** (`/invite/:token`): the page checks the link first ("Checking your invite…").
  - Good link: title "Join <studio>". Line (muted): "<Name> invited you to <studio> as an editor. Your email is <email>." Fields: Your name, Choose a password. Button **Create my account**.
  - Used, expired or made-up link: "Invite not valid" / "This invite link is not valid any more." / "Ask whoever invited you to send a new link." / "Already have an account? Sign in". No form.
  - The check itself fails (no connection, server error): "Could not check your invite" / "Check your connection and try again." with **Try again**. Never say the link is dead unless it is.

## States and copy
- Wrong details: banner (danger) inside the card "Email or password is wrong." Do not say which.
- Throttled: "Too many tries. Wait a minute and try again." Button disabled with that reason below it.
- Busy: button "Signing in…" with spinner, inputs disabled.
- After signing in: return to the page they came from, else Projects of the last brand used.
