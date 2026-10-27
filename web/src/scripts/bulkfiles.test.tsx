import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { BulkCreate } from "./BulkCreate";
import type { Uploader } from "./videoUploads";

const owner = { id: 1, email: "r@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const MB = 1024 * 1024;
const video = (name: string, size = 5 * MB, type = "video/mp4") => Object.defineProperty(new File([new Uint8Array(8)], name, { type }), "size", { value: size });

/** A stand-in uploader that finishes when told to, and notes what it was asked to send. */
function stand() {
  const sent: string[] = [];
  const pending: { file: File; progress: (p: number) => void; done: (r: { id: string; seconds: number | null; problem?: string | null }) => void; fail: () => void; signal: AbortSignal }[] = [];
  const uploader: Uploader = (file, progress, signal) =>
    new Promise((resolve, reject) => {
      sent.push(file.name);
      pending.push({ file, progress, done: resolve, fail: () => reject(new Error("x")), signal });
    });
  return { uploader, sent, pending };
}

function open(uploader: Uploader, onClose = () => {}) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <BulkCreate brandId={1} onClose={onClose} uploader={uploader} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const toReels = async () => userEvent.click(await screen.findByRole("radio", { name: "Reels" }));
// The picker's own filter is off here: a person can still choose "All files", so the check on the file itself has to hold.
const drop = async (...files: File[]) => userEvent.setup({ applyAccept: false }).upload(screen.getByLabelText("Video files"), files);

afterEach(() => vi.unstubAllGlobals());
const setup = () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /references": [200, []], "GET /credits/me": [200, null] });
};

test("a video added to Reels uploads at once, shows its progress, and is Ready when done; the button counts it", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  expect(screen.getByRole("button", { name: /^Make 0 drafts/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /^Make 0 drafts/ })).toHaveAccessibleDescription("Add a reel link or a video first");
  await drop(video("bo-tries-salmon.mp4"));
  expect(up.sent).toEqual(["bo-tries-salmon.mp4"]);
  up.pending[0].progress(62);
  expect(await screen.findByText("Uploading… 62%")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make 0 drafts/ })).toHaveAccessibleDescription("Wait for the uploads to finish (1 left)");
  up.pending[0].done({ id: "u1", seconds: 38 });
  expect(await screen.findByText("Ready")).toBeInTheDocument();
  expect(screen.getByText("38 s · 5 MB")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make 1 draft" })).toBeEnabled();
});

test("a file that isn't MP4 or MOV, or is over 100 MB, is refused on its own row before anything is sent", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("notes.pdf", 1000, "application/pdf"), video("huge.mp4", 101 * MB));
  expect(await screen.findByText("Only MP4 or MOV videos can be read.")).toBeInTheDocument();
  expect(screen.getByText("This one is over 100 MB.")).toBeInTheDocument();
  expect(up.sent).toEqual([]); // nothing was sent
  expect(screen.getByText("2 files won't be added.")).toBeInTheDocument();
});

test("a video over 90 seconds is refused after the upload, and the server's own sentence shows too", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("long.mp4"), video("odd.mov", 3 * MB, "video/quicktime"));
  up.pending[0].done({ id: "u1", seconds: 120 });
  up.pending[1].done({ id: "u2", seconds: null, problem: "We couldn't read this video." });
  expect(await screen.findByText("This one is longer than 90 seconds.")).toBeInTheDocument();
  expect(screen.getByText("We couldn't read this video.")).toBeInTheDocument();
});

test("a failed upload says so and can be tried again", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("bo.mp4"));
  up.pending[0].fail();
  expect(await screen.findByText("The upload didn't finish.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(up.sent).toEqual(["bo.mp4", "bo.mp4"]);
  up.pending[1].done({ id: "u1", seconds: 20 });
  expect(await screen.findByText("Ready")).toBeInTheDocument();
});

test("the same file twice isn't added again, and past 20 reels the extra files are named", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("a.mp4"));
  await drop(video("a.mp4"));
  expect(await screen.findByText("a.mp4 is already in the list.")).toBeInTheDocument();
  expect(up.sent).toEqual(["a.mp4"]);
  await drop(...Array.from({ length: 22 }, (_, i) => video(`f${i}.mp4`, (i + 1) * MB)));
  expect(await screen.findByText("Up to 20 reels at once. 3 files weren't added.")).toBeInTheDocument();
  expect(up.sent).toHaveLength(20);
});

test("Remove stops an upload that is running and drops the file", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("bo.mp4"));
  await userEvent.click(screen.getByRole("button", { name: "Remove bo.mp4" }));
  expect(up.pending[0].signal.aborted).toBe(true);
  expect(screen.queryByText("bo.mp4")).toBeNull();
});

test("closing while files are still uploading asks first; Keep uploading is the way back", async () => {
  setup();
  const up = stand();
  const onClose = vi.fn();
  open(up.uploader, onClose);
  await toReels();
  await drop(video("bo.mp4"));
  await userEvent.click(screen.getByRole("button", { name: /close/i }));
  const dialog = await screen.findByRole("alertdialog", { name: "Stop the uploads?" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Keep uploading" }));
  expect(onClose).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /close/i }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Stop and close" }));
  expect(onClose).toHaveBeenCalled();
});
