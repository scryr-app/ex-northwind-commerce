import * as Sentry from "@sentry/react";

export function initializeMonitoring() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_APP_ENV ?? "local",
    release: import.meta.env.VITE_RELEASE || undefined,
    tracesSampleRate: 0.1,
    sendDefaultPii: false
  });

  if (
    import.meta.env.VITE_SENTRY_TEST_ENABLED === "true" &&
    new URLSearchParams(window.location.search).get("sentry-test") === "1"
  ) {
    queueMicrotask(() => {
      throw new Error("Controlled Northwind frontend Sentry test error");
    });
  }
}

export { Sentry };
