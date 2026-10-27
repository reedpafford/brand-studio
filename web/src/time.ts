/** A server time as a Date. The server writes UTC with a "Z"; a time without a zone is read as UTC too, never local. */
export const serverTime = (iso: string) => new Date(iso.includes("T") && !/(Z|[+-]\d\d:?\d\d)$/i.test(iso) ? `${iso}Z` : iso);
