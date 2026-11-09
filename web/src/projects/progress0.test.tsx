import { expect, test } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePanelFacts } from "../videos/Preview";
import { fakeServer } from "../test/server";

test("Polish: before its video loads, the page asks for no project 0 (was six 404s on every load)", async () => {
  const calls = fakeServer({});
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
  renderHook(() => usePanelFacts(0), { wrapper });
  await new Promise((r) => setTimeout(r, 50));
  expect(calls.filter((c) => /\/projects\/0\//.test(c.url))).toEqual([]);
});
