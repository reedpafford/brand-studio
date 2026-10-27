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
  const pending: { file: File; progress: (p: number) => void; done: (r: { id: number | null; seconds: number | null; problem?: string | null }) => void; fail: () => void; signal: AbortSignal }[] = [];
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
  up.pending[0].done({ id: 1, seconds: 38 });
  expect(await screen.findByText("Ready")).toBeInTheDocument();
  expect(screen.getByText("38 s · 5 MB")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make 1 draft" })).toBeEnabled();
});

test("a video dropped outside the zone adds nothing and the browser is told not to open it", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  const file = video("stray.mp4");
  for (const type of ["dragover", "drop"]) {
    const ev = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(ev, "dataTransfer", { value: { files: [file] } });
    screen.getByText("Bulk create").dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
  }
  expect(up.sent).toEqual([]);
  expect(screen.queryByText("stray.mp4")).not.toBeInTheDocument();
});

test("a refused file takes no place out of the 20, so removing nothing still lets good files in", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("a.txt", 5 * MB, "text/plain"));
  const good = Array.from({ length: 20 }, (_, i) => video(`v${i}.mp4`));
  await drop(...good);
  expect(up.sent).toHaveLength(20);
});

test("links pasted after files share the 20 cap: Make is disabled with the reason, and removing one clears it", async () => {
  setup();
  const up = stand();
  open(up.uploader);
  await toReels();
  await drop(video("a.mp4"));
  up.pending[0].done({ id: 1, seconds: 10 });
  await screen.findByText("Ready");
  await userEvent.click(screen.getByLabelText("Paste reel links, one per line"));
  await userEvent.paste(Array.from({ length: 20 }, (_, i) => `https://www.instagram.com/reel/r${i}/`).join("\n"));
  const make = screen.getByRole("button", { name: /^Make 21 drafts/ });
  expect(make).toBeDisabled();
  expect(make).toHaveAccessibleDescription("Up to 20 reels at once: remove 1");
  expect(screen.getByText("That's 21 reels. Up to 20 at a time.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove a.mp4" }));
  expect(screen.queryByText(/Up to 20 at a time/)).toBeNull();
});

test("closing without making drafts deletes the files that were kept", async () => {
  setup();
  const calls = fakeServer({ "GET /auth/me": [200, owner], "GET /references": [200, []], "GET /credits/me": [200, null], "DELETE /uploads/7": [204, null] });
  const up = stand();
  const onClose = vi.fn();
  open(up.uploader, onClose);
  await toReels();
  await drop(video("a.mp4"));
  up.pending[0].done({ id: 7, seconds: 10 });
  await screen.findByText("Ready");
  await userEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(onClose).toHaveBeenCalled();
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /uploads/7")).toBe(true));
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
  up.pending[0].done({ id: 1, seconds: 120 });
  up.pending[1].done({ id: 2, seconds: null, problem: "We couldn't read this video." });
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
  up.pending[1].done({ id: 1, seconds: 20 });
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

test("links and videos go to the server as one ordered list, a refused video is never sent, and the drafts say Link or Video with the price for both", async () => {
  setViewport(1440);
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /references": [200, []],
    "GET /credits/me": [200, null],
    "POST /scripts/bulk": [201, [
      { id: 11, title: "Untitled reel", reel: { status: "preparing", seconds: null, source: "link", url: "https://www.instagram.com/reel/Abc123/", file_name: null } },
      { id: 12, title: "Untitled reel", reel: { status: "preparing", seconds: 38, source: "file", url: null, file_name: "bo-tries-salmon.mp4" } },
    ]],
    "POST /scripts/write/estimate": [200, { count: 2, credits: 49, credits_left: null, reading: 2, read_credits: 7, writing: 2, write_credits: 42, waiting: [], failed: [], reels: { links: 1, videos: 1 } }],
  });
  const up = stand();
  open(up.uploader);
  await toReels();
  await userEvent.type(screen.getByLabelText("Paste reel links, one per line"), "https://www.instagram.com/reel/Abc123/");
  await drop(video("bo-tries-salmon.mp4"), video("refused.mp4"));
  up.pending[0].done({ id: 7, seconds: 38 });
  up.pending[1].done({ id: null, seconds: 120, problem: "This video is 2 minutes long; reels up to 90 seconds can be read." });
  expect(await screen.findByText("This video is 2 minutes long; reels up to 90 seconds can be read.")).toBeInTheDocument();
  expect(screen.getByText("1 file won't be added.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make 2 drafts" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/bulk")?.body).toMatchObject({
    scripts: [{ brand_id: 1, reel_url: "https://www.instagram.com/reel/Abc123/" }, { brand_id: 1, upload_id: 7 }],
  }));
  expect((calls.find((c) => c.key === "POST /scripts/bulk")?.body as { scripts: unknown[] }).scripts).toHaveLength(2); // the refused one was left out
  expect(await screen.findByText("Video · 38 s")).toBeInTheDocument();
  expect(screen.getByText("bo-tries-salmon.mp4")).toBeInTheDocument();
  expect(screen.getByText(/About 49 credits: reading 1 reel link and 1 video \(7\) and writing 2 scripts and casts \(42\)/)).toBeInTheDocument();
});

test("the server's plain sentence for a batch that is still being prepared is shown as it comes", async () => {
  setViewport(1440);
  fakeServer({
    "GET /auth/me": [200, owner],
    "GET /references": [200, []],
    "GET /credits/me": [200, null],
    "POST /scripts/bulk": [409, { detail: "Your last reels are still being prepared. Try again when they're done." }],
  });
  open(stand().uploader);
  await toReels();
  await userEvent.type(screen.getByLabelText("Paste reel links, one per line"), "https://www.instagram.com/reel/Abc123/");
  await userEvent.click(screen.getByRole("button", { name: "Make 1 draft" }));
  expect(await screen.findByText("Your last reels are still being prepared. Try again when they're done.")).toBeInTheDocument();
});
