"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

// Retry / Resume for errored or interrupted sprints (proxied server-side).
export function SprintActions({ sprintId }: { sprintId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  async function act(action: "retry" | "resume") {
    setBusy(action);
    setMsg("");
    try {
      const res = await fetch(`/api/sprints/${sprintId}/${action}`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "Failed");
      setMsg("Restarting…");
      setTimeout(() => router.refresh(), 1500);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed");
      setBusy("");
    }
  }

  return (
    <div className="flex items-center gap-3">
      {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
      <Button variant="outline" onClick={() => act("resume")} disabled={!!busy}>
        {busy === "resume" ? "Resuming…" : "Resume"}
      </Button>
      <Button onClick={() => act("retry")} disabled={!!busy}>
        {busy === "retry" ? "Retrying…" : "Retry"}
      </Button>
    </div>
  );
}
