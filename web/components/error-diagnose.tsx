"use client";

import { useState } from "react";

// "Diagnose" control on each error row in the Activity timeline. Asks ADAM to analyze
// the error against its own troubleshooting runbook and returns a likely cause + fix
// steps — the Jul-17 ask (analyze, don't just report). Result is cached on the event,
// so a previously-diagnosed error shows instantly without re-billing.
type Diagnosis = {
  likely_cause?: string;
  fix_steps?: string[];
  confidence?: "high" | "medium" | "low";
  runbook_case?: string;
  needs_engineer?: boolean;
};

const CONF: Record<string, string> = {
  high: "text-[#14A800]",
  medium: "text-amber-600",
  low: "text-muted-foreground",
};

export function ErrorDiagnose({ eventId, cached }: { eventId: number; cached?: Diagnosis | null }) {
  const [diag, setDiag] = useState<Diagnosis | null>(cached ?? null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(force = false) {
    setLoading(true);
    setError(null);
    setOpen(true);
    try {
      const res = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, force }),
      });
      const data = await res.json();
      if (!res.ok || data.error) setError(data.error || `Request failed (${res.status})`);
      else setDiag(data.diagnosis);
    } catch {
      setError("Couldn’t reach the diagnosis service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-1.5 w-full">
      <div className="flex items-center gap-2">
        {!diag && !open && (
          <button
            onClick={() => run(false)}
            className="rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted"
          >
            🔍 Diagnose
          </button>
        )}
        {diag && !open && (
          <button onClick={() => setOpen(true)} className="text-xs text-[#14A800] hover:underline">
            Show diagnosis
          </button>
        )}
        {open && (
          <button onClick={() => setOpen(false)} className="text-xs text-muted-foreground hover:underline">
            Hide
          </button>
        )}
      </div>

      {open && (
        <div className="mt-2 rounded-lg border bg-background p-3 text-sm">
          {loading && <div className="text-muted-foreground">ADAM is diagnosing…</div>}
          {error && <div className="text-red-600">{error}</div>}
          {diag && !loading && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Likely cause
                </span>
                {diag.confidence && (
                  <span className={`text-xs font-medium ${CONF[diag.confidence] ?? ""}`}>
                    {diag.confidence} confidence
                  </span>
                )}
                {diag.needs_engineer && (
                  <span className="rounded-full border border-amber-400/40 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                    needs an engineer
                  </span>
                )}
              </div>
              <p>{diag.likely_cause}</p>
              {diag.fix_steps && diag.fix_steps.length > 0 && (
                <div>
                  <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Fix</div>
                  <ol className="mt-1 list-decimal space-y-1 pl-5">
                    {diag.fix_steps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                </div>
              )}
              <div className="flex items-center gap-3 pt-1 text-xs text-muted-foreground">
                {diag.runbook_case && diag.runbook_case !== "none" && (
                  <span>
                    Runbook: <a href="/wiki/16-fixing-errors" className="text-[#14A800] hover:underline">{diag.runbook_case}</a>
                  </span>
                )}
                <button onClick={() => run(true)} className="hover:text-foreground hover:underline">
                  Re-run
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
