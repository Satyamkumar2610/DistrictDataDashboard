import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import { ApiError } from "./api";
import "./theme.css";

const saved = (() => { try { return localStorage.getItem("theme"); } catch { return null; } })();
const dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
document.documentElement.dataset.theme = dark ? "dark" : "light";

// A data router, so links and navigations can run as View Transitions (motion.ts); the routes themselves live in App.
const router = createBrowserRouter([{ path: "*", element: <App /> }]);

// Retry once, and only what a retry can fix: an outage or a 5xx, never a 404 (that is an answer)
const queries = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, refetchOnWindowFocus: false,
  retry: (n, e) => n < 1 && (!(e instanceof ApiError) || e.transient) } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queries}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
