"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

// Approving a gate is a real mutation — it drives the live pipeline. The POST is
// proxied through /api/approve (server-side) so the API key never hits the browser.
export function GateActions({ sprintId, gateNum }: { sprintId: string; gateNum: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function approve() {
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sprintId, gateNum }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || `Failed (${res.status})`);
      }
      setMsg("Approved — advancing…");
      // Give the pipeline a moment, then re-fetch the server component.
      setTimeout(() => router.refresh(), 1500);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
      <Button onClick={approve} disabled={busy}>
        {busy ? "Working…" : `Approve gate ${gateNum}`}
      </Button>
    </div>
  );
}
