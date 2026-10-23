import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { applyTheme, getTheme } from "./theme";
import "@fontsource-variable/inter";
import "@fontsource/courier-prime/400.css";
import "@fontsource/courier-prime/700.css";
import "./styles/index.css";

applyTheme(getTheme());

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
