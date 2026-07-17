"use client";

import { useState } from "react";

// Small client button that copies a plaintext blob to the clipboard — used on the
// Digest page so Bree can paste the weekly summary straight into the change log / Slack.
export function CopyTextButton({ text, label = "Copy for Slack" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 2000);
        } catch {
          // ignore — clipboard may be blocked; the text is visible below to select manually
        }
      }}
      className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted"
    >
      {done ? "Copied ✓" : label}
    </button>
  );
}
