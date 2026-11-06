import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";
import { editor, owner } from "../test/people";
import { fakeServer } from "../test/server";
import { Scorecard } from "./Scorecard";

const renderWithClient = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
const card = { forecast_credits: 36.9, forecast_basis: "estimate", actual_credits: 109.5, director_credits: 76.8, within_forecast: false, words_exact: true, must_show_ok: true, score: null, note: null };
const head = (rate: number | null) => ({ title: "T", status: { kind: "delivered", words: "Delivered", reason: null, at: null, made: 0, total: 0 }, spent: { credits: 109.5, usd: rate && 11.26 }, up_to: null, budget: { credits: 164, usd: rate && 16.86 }, folder: null, format: "", style: "", seconds: 7, song: false, usd_per_credit: rate });

test("Flow-QA S2: the scorecard's forecast and spend are dollars to the owner, credits to an editor", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /projects/50/scorecard": [200, card], "GET /projects/50/idea": [200, head(0.1028)] });
  const view = renderWithClient(<Scorecard projectId={50} />);
  expect(await screen.findByText(/Forecast \$3\.80 \(estimate\)\. Spent \$11\.26 \(\$7\.90 the director's own\)/)).toBeInTheDocument();
  view.unmount();
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/50/scorecard": [200, card], "GET /projects/50/idea": [200, head(null)] });
  renderWithClient(<Scorecard projectId={50} />);
  expect(await screen.findByText(/Forecast 37 credits/)).toBeInTheDocument();
  expect(screen.queryByText(/\$/)).toBeNull();
});
