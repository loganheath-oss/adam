"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Status = { message?: string; item_index?: number; item_total?: number; item_label?: string };

// Live progress via the pipeline-events SSE. Only streams while the sprint is
// actively running; when the backend signals done (a gate or terminal state),
// it refreshes the page to pick up the new state.
export function SprintProgress({ sprintId, running }: { sprintId: string; running: boolean }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>({});

  useEffect(() => {
    if (!running) return;
    const es = new EventSource(`/api/sprints/${sprintId}/events`);
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        if (evt.type === "status") setStatus(evt);
        else if (evt.type === "done") {
          es.close();
          router.refresh();
        }
      } catch {
        /* ignore heartbeats / partials */
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [sprintId, running, router]);

  if (!running) return null;
  const label = status.message || "Working…";
  const items = status.item_total ? ` · ${status.item_index ?? 0}/${status.item_total} ${status.item_label ?? ""}` : "";

  return (
    <div className="mb-6 flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
      <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary" />
      <span className="text-sm font-medium">{label}<span className="text-muted-foreground">{items}</span></span>
    </div>
  );
}
