import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";

/* Fonts are self-hosted, not pulled from a CDN. A pharmacy in Nyamirambo on a
   weak connection must not wait on fonts.googleapis.com to render a price, and
   the till has to work when the line is down at all. Inter Variable ships the
   whole weight axis in one file, and carries the tabular-figure feature the
   money columns depend on. */
import "@fontsource-variable/inter";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./index.css";
import { initTheme } from "./lib/theme";

/* Before first paint, so the page never flashes the wrong theme on the way in. */
initTheme();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
