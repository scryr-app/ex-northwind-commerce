import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initializeAnalytics } from "./analytics";
import { initializeMonitoring, Sentry } from "./monitoring";
import "./styles.css";

initializeAnalytics();
initializeMonitoring();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<p>Northwind Commerce could not load.</p>}>
      <App />
    </Sentry.ErrorBoundary>
  </React.StrictMode>
);
