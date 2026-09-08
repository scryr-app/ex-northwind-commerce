import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initializeAnalytics } from "./analytics";
import "./styles.css";

initializeAnalytics();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
