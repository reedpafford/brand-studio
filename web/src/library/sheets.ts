import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** The picture model a Cast & places sheet is drawn with. */
export const SHEET_MODEL = "nano-banana-pro" as const;
const RESOLUTION = "2K";
/** The most a sheet's "What should change?" note may be, as the server's (app/routes/sheets.py SheetIn.change). */
export const SHEET_NOTE = 500;

/** The look check in words: what the look reads as and what doesn't fit ("…a man in his 50s, but Mia is a woman in her late 20s."). */
export const lookFitNote = (fit: { seen: string; problem: string }) => {
  const bare = (t: string) => t.trim().replace(/[.\s]+$/, "");
  return `This look reads as ${bare(fit.seen)}${bare(fit.problem) ? `, but ${bare(fit.problem)}` : ""}.`;
};

/** What drawing one sheet costs, in credits (undefined until the prices load). */
export function useSheetPrice() {
  const models = useQuery({ queryKey: ["models"], queryFn: async () => (await api.GET("/models")).data ?? [] });
  return { model: SHEET_MODEL, price: models.data?.find((m) => m.id === SHEET_MODEL)?.credits_per_unit?.[RESOLUTION] };
}
