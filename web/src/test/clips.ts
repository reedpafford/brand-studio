import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** On the video's Clips tab: picks a clip in the list ("c2"), so its card and still show on the right. */
export async function pickClip(clipId: string) {
  const list = await screen.findByRole("list", { name: "Clip list" });
  const row = await within(list).findByRole("button", { name: new RegExp(`^Clip ${clipId.replace(/^c/, "")}(\\D|$)`) });
  if (row.getAttribute("aria-current") !== "true") await userEvent.click(row);
}

/** Picks a clip in the list and returns its card. */
export async function clipCard(clipId: string) {
  await pickClip(clipId);
  return screen.findByLabelText(`Clip ${clipId}`);
}
