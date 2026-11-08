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
}

export { Sentry };
