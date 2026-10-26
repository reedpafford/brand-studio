# Sign in, first-time setup, join from an invite

These pages have no shell. Each is one centred card, 420px wide, on `bg-bg`.
- Above the card: a small "Brand Studio" wordmark (Manrope 800, 20px).
- Below the card: a theme-matched footnote, "Made for Reed's studio."
- **Phone:** the card runs full width with 16px gutters, starting 64px from the top. Fields and buttons are 44px.

All labels below are the ones the e2e tests use today. Keep them exactly.

## Sign in (`/login`)
- Title (page role, 32): **Sign in**.
- Fields: **Email** (`autocomplete=email`, `type=email`) and **Password**. The password field has an eye icon button inside it, `aria-label="Show password"`.
- Amber button, full width: **Sign in**. While busy, **Signing in…** with the spinning loader; the fields are disabled.
- Under the button (meta): "Forgot your password? Ask Reed."
- **Error:** a danger banner inside the card, "Wrong email or password." Focus moves to Email.
- **Throttled:** "Too many tries. Wait a minute and try again." The button is disabled and shows that reason under it.
- **Success:** go to the page they came from, or else the Videos of the last brand used.

## First-time setup (`/setup`)
- Title: **Set up the studio**.
- Fields:
  - **Setup code (from your server settings)**
  - **Studio name**, with the hint "What your team sees when they're invited, e.g. Reed's studio." It's a plain name with spaces and capitals, never a slug.
  - **Your name**
  - **Email**
  - **Password (10 or more characters)**: the counter turns `success` at 10 or more.
- Amber button: **Create owner account**.
- Errors appear in a danger banner, using the server's own words: "Setup is not allowed." / "Already set up."
- Footer link: "Already set up? **Sign in**".

## Join from an invite (`/invite/:token`)
- **Checking:** a skeleton card (title bar plus two field bars). After 1s it adds "Checking your invite…".
- **Good link:**
  - Title: **Join {studio}**, using the studio's name as typed ("Join Reed's studio"). If the stored name looks like a slug (no spaces, with dashes, like "owner-reed"), show **Join {owner name}'s studio** instead ("Join Reed's studio"), and use the same words in the line below.
  - Line (meta): "{Name} invited you to {studio} as an editor. Your email is {email}."
  - Fields: **Your name**, **Choose a password (10 or more characters)**.
  - Amber button: **Create my account**.
  - **Success:** lands on Videos for the first brand. A toast says "Welcome to {studio}, {name}."
- **Dead link** (404):
  - `Link2Off` icon in muted colour, then the headline **Invite not valid**.
  - Body: "This invite link is not valid any more."
  - Meta: "Ask whoever invited you to send a new link."
  - Then "Already have an account? **Sign in**". No form.
- **Check failed** (no connection or server error):
  - Headline **Could not check your invite**.
  - Body: "Check your connection and try again."
  - Amber button **Try again**.
