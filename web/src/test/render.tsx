import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { App } from "../App";

/** The whole app at one address, with a fresh cache, in a data router as the app runs (main.tsx). */
export function renderApp(path: string) {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
