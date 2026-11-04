import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { App } from "./App";
import { applyTheme, getTheme } from "./theme";
import "./styles/index.css";

applyTheme(getTheme());

const queryClient = new QueryClient();
// A data router around the app's own routes, so a page can ask before a way out loses its changes (useBlocker).
const router = createBrowserRouter([{ path: "*", element: <App /> }]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
