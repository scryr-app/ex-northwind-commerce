import { useEffect, useRef } from "react";

declare global {
  interface Window {
    turnstile?: { render: (element: HTMLElement, options: Record<string, unknown>) => string };
  }
}

export function Turnstile({ onToken }: { onToken: (token: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const sitekey = import.meta.env.VITE_TURNSTILE_SITE_KEY;

  useEffect(() => {
    if (!sitekey || !container.current) return;
    const render = () => window.turnstile?.render(container.current!, {
      sitekey,
      callback: onToken,
      "expired-callback": () => onToken("")
    });
    if (window.turnstile) render();
    else {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      script.onload = render;
      document.head.appendChild(script);
      return () => script.remove();
    }
  }, [onToken, sitekey]);

  return sitekey ? <div ref={container} aria-label="Checkout verification" /> : null;
}
