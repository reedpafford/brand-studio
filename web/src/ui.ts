/** Shared class strings for the Designer's components (docs/design/README.md). */
export const input = "min-h-11 w-full rounded-sm border border-border-strong bg-surface px-3 py-2 text-base text-text sm:min-h-0";
export const btnPrimary =
  "rounded-md border border-accent-border bg-accent px-4 py-2 font-medium text-on-accent hover:bg-accent-hover disabled:cursor-not-allowed disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text";
export const btnSecondary = "rounded-md border border-border-strong bg-surface px-4 py-2 font-medium text-text disabled:cursor-not-allowed disabled:bg-disabled disabled:text-disabled-text";
export const card = "rounded-md border border-border bg-surface p-4 sm:p-6";
export const linkText = "text-accent-text underline disabled:cursor-not-allowed disabled:text-disabled-text disabled:no-underline"; // amber text only reads on dark; accent-text is the readable variant in both modes
/** "← Scripts" (a back link) at the top of a page: 44px tall on phones. */
export const backLink = `${linkText} inline-flex min-h-11 items-center sm:min-h-0`;
export const errorText = "text-sm text-danger";
export const pageTitle = "text-[length:var(--text-lg)] font-semibold";
