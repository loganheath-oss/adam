"use client";

import { useEffect } from "react";

// Root error boundary: catches any uncaught render/runtime error in the app, reports
// it to the Activity timeline (via /api/client-error → backend), and shows a minimal
// recover screen. Built for August — a UI crash lands as an error.client event
// instead of a blank white page nobody can diagnose.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    try {
      fetch("/api/client-error", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: typeof window !== "undefined" ? window.location.pathname : "",
          error: String(error?.message ?? error),
          digest: error?.digest ?? "",
        }),
        keepalive: true,
      }).catch(() => {});
    } catch {
      // never let reporting throw
    }
  }, [error]);

  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600 }}>Something went wrong</h1>
        <p style={{ marginTop: "0.75rem", color: "#666" }}>
          This page hit an error. It’s been logged to the Activity timeline. Try again, and if it keeps
          happening, file it under Issues with what you were doing.
        </p>
        <button
          onClick={() => reset()}
          style={{
            marginTop: "1.25rem",
            background: "#14A800",
            color: "white",
            border: 0,
            borderRadius: 8,
            padding: "0.6rem 1.2rem",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
