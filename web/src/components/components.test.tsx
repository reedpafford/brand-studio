import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Clapperboard } from "lucide-react";
import { afterEach, expect, test, vi } from "vitest";
import { Badge, Banner, Button, Card, Dialog, EmptyState, Field, MediaCard, Select, Sheet, SidePanel, Skeleton, StepPicker, Tabs, TextArea, ToastProvider, creditsLabel, useToast, wholeCredits, type Step } from ".";

afterEach(() => vi.useRealTimers());

test("prices are whole credits, rounded up, and zero is free", () => {
  expect(wholeCredits(67.5)).toBe(68);
  expect(wholeCredits(8)).toBe(8);
  expect(wholeCredits(0.2)).toBe(1);
  expect(creditsLabel(67.5)).toBe("68 credits");
  expect(creditsLabel(1)).toBe("1 credit");
  expect(creditsLabel(0)).toBe("free");
});

test("a paid button says its price inside", () => {
  const { rerender } = render(<Button price={7.2}>Make the takes</Button>);
  expect(screen.getByRole("button", { name: "Make the takes · 8 credits" })).toBeEnabled();
  rerender(<Button price={0}>Make the video</Button>);
  expect(screen.getByRole("button", { name: "Make the video · free" })).toBeInTheDocument();
});

test("a disabled button says why on the line under it, and a busy one cannot be pressed twice", async () => {
  const click = vi.fn();
  const { rerender } = render(
    <Button disabled reason="Approve every clip first (2 left)" onClick={click}>
      Make the video
    </Button>,
  );
  const button = screen.getByRole("button", { name: "Make the video" });
  expect(button).toBeDisabled();
  expect(button).toHaveAccessibleDescription("Approve every clip first (2 left)");
  rerender(
    <Button busy onClick={click}>
      Making…
    </Button>,
  );
  // Busy keeps its look (an amber button stays amber) and ignores presses; it is not "disabled".
  expect(screen.getByRole("button", { name: "Making…" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Making…" })).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("button", { name: "Making…" })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByRole("button", { name: "Making…" }).className).toContain("bg-accent");
  await userEvent.click(screen.getByRole("button", { name: "Making…" }));
  expect(click).not.toHaveBeenCalled();
});

test("every button is at least 44px; a dense secondary drops to 36px only from lg (the rail layout) up", () => {
  render(
    <>
      <Button>Primary</Button>
      <Button variant="secondary" dense>
        Dense
      </Button>
      <Button variant="primary" dense>
        Dense primary
      </Button>
    </>,
  );
  expect(screen.getByRole("button", { name: "Primary" }).className).toContain("min-h-control");
  expect(screen.getByRole("button", { name: "Dense" }).className).toContain("min-h-control");
  expect(screen.getByRole("button", { name: "Dense" }).className).toContain("lg:min-h-control-dense");
  expect(screen.getByRole("button", { name: "Dense primary" }).className).not.toContain("control-dense"); // amber buttons are always 44px
});

test("fields are labelled, show a counter, and an error replaces the hint and is tied to the field", () => {
  render(
    <>
      <TextArea label="What's it for?" counter="78 / 2,000" hint="A few lines is enough." />
      <Field label="Planned length (seconds)" error="This plan would cost more than one video can." defaultValue="400" />
      <Select label="Where will it be posted?">
        <option>TikTok</option>
      </Select>
    </>,
  );
  expect(screen.getByLabelText("What's it for?")).toHaveAccessibleDescription("A few lines is enough.");
  expect(screen.getByText("78 / 2,000")).toBeInTheDocument();
  const length = screen.getByLabelText("Planned length (seconds)");
  expect(length).toBeInvalid();
  expect(length).toHaveAccessibleDescription("This plan would cost more than one video can.");
  expect(screen.getByRole("combobox", { name: "Where will it be posted?" })).toBeInTheDocument();
});

test("a badge says the status in words, and one over a picture is white on black", () => {
  render(
    <>
      <Badge tone="warning">Waiting for Reed to approve</Badge>
      <Badge tone="media">Clips</Badge>
    </>,
  );
  expect(screen.getByText("Waiting for Reed to approve")).toBeInTheDocument();
  expect(screen.getByText("Clips").className).toContain("text-white");
  expect(screen.getByText("Clips").className).toContain("bg-black/60");
});

test("a media card with no picture has no shade, normal text colours and the kind's icon in the middle", () => {
  render(<MediaCard title="Bo" meta="Character" icon={Clapperboard} />);
  expect(document.querySelector('[class*="media-shade"]')).not.toBeInTheDocument();
  expect(screen.getByText("Bo").parentElement?.className).toContain("text-text");
  expect(screen.getByText("Bo").parentElement?.className).not.toContain("text-on-media");
  expect(document.querySelector("svg")).toBeInTheDocument();
});

test("a media card leads with the picture: title on it, badge on it, play only when it plays", async () => {
  const open = vi.fn();
  const { rerender } = render(<MediaCard title="Bo tries salmon" meta="2 of 3 clips approved" badge={<Badge tone="success">Ready</Badge>} image="/api/files/9" playable onOpen={open} />);
  const card = screen.getByRole("button", { name: "Bo tries salmon" });
  expect(within(card).getByText("Ready")).toBeInTheDocument();
  expect(within(card).getByText("2 of 3 clips approved")).toBeInTheDocument();
  expect(card.querySelector("img")).toHaveAttribute("src", "/api/files/9");
  expect(card.querySelector("svg")).toBeInTheDocument(); // the play button
  await userEvent.click(card);
  expect(open).toHaveBeenCalled();
  rerender(<MediaCard title="Bo" />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(document.querySelector("svg")).not.toBeInTheDocument();
});

test("a card is just a panel", () => {
  render(<Card>Inside</Card>);
  expect(screen.getByText("Inside")).toBeInTheDocument();
});

function Opener({ side }: { side?: boolean }) {
  const [open, setOpen] = useState(false);
  const Panel = side ? SidePanel : Sheet;
  return (
    <>
      <button onClick={() => setOpen(true)}>Open it</button>
      {open && (
        <Panel title="Needs a change" onClose={() => setOpen(false)}>
          <label>
            What's wrong?
            <textarea />
          </label>
          <button>Redo · 4 credits</button>
        </Panel>
      )}
    </>
  );
}

test("a sheet traps focus, closes on Escape, and gives focus back to the button that opened it", async () => {
  render(<Opener />);
  const opener = screen.getByRole("button", { name: "Open it" });
  await userEvent.click(opener);
  const dialog = screen.getByRole("dialog", { name: "Needs a change" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  // focus starts inside, and Tab wraps around inside
  expect(dialog.contains(document.activeElement)).toBe(true);
  for (let i = 0; i < 6; i++) {
    await userEvent.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
  }
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
});

test("tapping outside closes a side panel too", async () => {
  render(<Opener side />);
  await userEvent.click(screen.getByRole("button", { name: "Open it" }));
  expect(screen.getByRole("dialog", { name: "Needs a change" })).toBeInTheDocument();
  // One "Close" per overlay (the X); the dimmed backdrop is not a second button but still closes it.
  expect(screen.getAllByRole("button", { name: "Close" })).toHaveLength(1);
  await userEvent.click(document.querySelector("[aria-hidden].fixed.inset-0") as HTMLElement);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("a dialog asks first, and says what is lost; Keep it cancels", async () => {
  const yes = vi.fn();
  const no = vi.fn();
  render(
    <Dialog title="Delete the screen “Home”?" actionLabel="Delete screen" danger onConfirm={yes} onCancel={no}>
      Videos already made keep it.
    </Dialog>,
  );
  expect(screen.getByRole("alertdialog", { name: "Delete the screen “Home”?" })).toBeInTheDocument();
  expect(screen.getByText("Videos already made keep it.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Keep it" }));
  expect(no).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Delete screen" }));
  expect(yes).toHaveBeenCalledTimes(1);
});

function Shout({ undo, kind, long }: { undo?: () => void; kind?: "success" | "error"; long?: boolean }) {
  const toast = useToast();
  return <button onClick={() => toast("Approved. Sam's clip is rendering.", undo, kind, long)}>Say it</button>;
}

test("a toast without Undo that asks for more time stays 8 seconds, like one with Undo", () => {
  vi.useFakeTimers();
  render(
    <ToastProvider>
      <Shout long />
    </ToastProvider>,
  );
  act(() => screen.getByRole("button", { name: "Say it" }).click());
  act(() => {
    vi.advanceTimersByTime(7900);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Approved");
  act(() => {
    vi.advanceTimersByTime(200);
  });
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});

test("a toast is announced, goes after 4 seconds, and waits while you hover it", () => {
  vi.useFakeTimers();
  render(
    <ToastProvider>
      <Shout />
    </ToastProvider>,
  );
  expect(screen.getByRole("status")).toBeInTheDocument();
  act(() => screen.getByRole("button", { name: "Say it" }).click());
  expect(screen.getByRole("status")).toHaveTextContent("Approved. Sam's clip is rendering.");
  act(() => {
    vi.advanceTimersByTime(3900);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Approved");
  act(() => {
    vi.advanceTimersByTime(200);
  });
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});

test("a toast with Undo stays 8 seconds, pauses on hover, and Undo runs and closes it", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const undo = vi.fn();
  render(
    <ToastProvider>
      <Shout undo={undo} />
    </ToastProvider>,
  );
  act(() => screen.getByRole("button", { name: "Say it" }).click());
  act(() => {
    vi.advanceTimersByTime(5000);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Approved");
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  await user.hover(screen.getByText("Approved. Sam's clip is rendering."));
  act(() => {
    vi.advanceTimersByTime(20000);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Approved"); // paused
  await user.click(screen.getByRole("button", { name: "Undo" }));
  expect(undo).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});

test("a banner says what happened and offers the next step; an empty state has one button", async () => {
  const again = vi.fn();
  render(
    <>
      <Banner title="The breakdown didn't finish." action={<Button onClick={again}>Try again</Button>}>
        Nothing was charged.
      </Banner>
      <EmptyState icon={Clapperboard} title="No clips yet" action={<Button price={3}>Write clip prompts</Button>}>
        Each clip is made from its frame and the shots.
      </EmptyState>
      <Skeleton className="h-10" />
    </>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("The breakdown didn't finish.");
  expect(screen.getByRole("alert")).toHaveTextContent("Nothing was charged.");
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(again).toHaveBeenCalled();
  expect(screen.getByRole("heading", { name: "No clips yet" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Write clip prompts · 3 credits" })).toBeInTheDocument();
});

const steps: Step[] = [
  { id: "brief", label: "Brief", state: "done" },
  { id: "script", label: "Script", state: "done" },
  { id: "shots", label: "Shots", state: "stale" },
  { id: "storyboard", label: "Storyboard", state: "current" },
  { id: "clips", label: "Clips", state: "todo", reason: "Finish Storyboard first" },
  { id: "final", label: "Final video", state: "todo", reason: "Finish Clips first" },
];

test("the step picker shows done, current, out of date and locked steps, and a locked step cannot be opened", async () => {
  const pick = vi.fn();
  render(<StepPicker steps={steps} onPick={pick} />);
  const list = screen.getByRole("list", { name: "Steps" });
  expect(within(list).getByRole("button", { name: "Storyboard" })).toHaveAttribute("aria-current", "step");
  expect(within(list).getByRole("button", { name: "Shots · out of date" })).toBeInTheDocument();
  const locked = within(list).getByRole("button", { name: /Clips/ });
  expect(locked).toHaveAttribute("aria-disabled", "true");
  expect(locked).toHaveAttribute("title", "Finish Storyboard first");
  expect(locked).toHaveAccessibleDescription("Finish Storyboard first"); // not only a tooltip
  await userEvent.click(locked);
  expect(pick).not.toHaveBeenCalled();
  await userEvent.click(within(list).getByRole("button", { name: "Script" }));
  expect(pick).toHaveBeenCalledWith("script");
});

test("tabs show counts and tell you which is selected", async () => {
  const change = vi.fn();
  render(<Tabs label="Cast and places" value="characters" onChange={change} tabs={[{ id: "characters", label: "Characters", count: 5 }, { id: "places", label: "Places", count: 2 }]} />);
  expect(screen.getByRole("tab", { name: "Characters 5" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("tab", { name: "Places 2" }));
  expect(change).toHaveBeenCalledWith("places");
});

test("a toast stays while focus is inside it, even after the pointer leaves", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  render(
    <ToastProvider>
      <Shout undo={() => {}} />
    </ToastProvider>,
  );
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  act(() => screen.getByRole("button", { name: "Say it" }).click());
  const undo = screen.getByRole("button", { name: "Undo" });
  await user.hover(undo);
  act(() => undo.focus());
  await user.unhover(undo);
  act(() => {
    vi.advanceTimersByTime(30000);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Approved"); // focus still holds it
  act(() => undo.blur());
  act(() => {
    vi.advanceTimersByTime(8100);
  });
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});

test("a price not known yet holds its place with a grey slot, and the press waits for it", async () => {
  const press = vi.fn();
  render(
    <Button price={null} onClick={press}>
      Change it
    </Button>,
  );
  const b = screen.getByRole("button", { name: /Change it/ });
  expect(b).toHaveAccessibleName("Change it · price loading");
  await userEvent.click(b);
  expect(press).not.toHaveBeenCalled();
});

function Stacked() {
  const [panel, setPanel] = useState(false);
  const [list, setList] = useState(false);
  return (
    <>
      <Button onClick={() => setPanel(true)}>Open the panel</Button>
      {panel && (
        <SidePanel title="Make this version" onClose={() => setPanel(false)}>
          <Button onClick={() => setList(true)}>Shape</Button>
          {list && (
            <Sheet title="Shape" onClose={() => setList(false)}>
              <Button>9:16</Button>
            </Sheet>
          )}
        </SidePanel>
      )}
    </>
  );
}

test("Escape closes only the top overlay: a list opened over a panel goes, the panel stays (QA-3)", async () => {
  render(<Stacked />);
  await userEvent.click(screen.getByRole("button", { name: "Open the panel" }));
  await userEvent.click(screen.getByRole("button", { name: "Shape" }));
  expect(screen.getByRole("dialog", { name: "Shape" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "Shape" })).toBeNull();
  expect(screen.getByRole("dialog", { name: "Make this version" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
});
