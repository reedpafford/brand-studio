import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Elapsed, elapsed } from "./History";

test("elapsed time reads as seconds, then minutes", () => {
  expect(elapsed(45_000)).toBe("45s");
  expect(elapsed(80_000)).toBe("1m 20s");
  expect(elapsed(-5_000)).toBe("0s");
});

test("a run started a few seconds ago counts up in New York, even for a server time without a zone", () => {
  const tz = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    expect(new Date(2026, 0, 1).getTimezoneOffset()).toBe(300);
    const started = new Date(Date.now() - 5000).toISOString().replace("Z", ""); // how the server used to write it
    render(<Elapsed since={started} />);
    expect(Number(screen.getByText(/^\d+s$/).textContent!.replace("s", ""))).toBeGreaterThan(0);
  } finally {
    process.env.TZ = tz;
  }
});
