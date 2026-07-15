"use client";

import { useState } from "react";

const CATEGORIES = [
  ["quality", "Copy/creative quality"],
  ["wrong_output", "Wrong output"],
  ["error", "Error / it broke"],
  ["other", "Other"],
] as const;

// "Report an issue" — the capture end of the feedback→learning loop. Drop it on the
// admin Issues page or a sprint page (pass sprintId to attach the report to a sprint).
export function ReportIssue({ sprintId, compact }: { sprintId?: string; compact?: boolean }) {
  const [open, setOpen] = useState(!compact);
  const [desc, setDesc] = useState("");
  const [cat, setCat] = useState<string>("quality");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    if (!desc.trim()) return;
    setBusy(true);
    setErr("");
    try {
      const res = await fetch("/api/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: desc, category: cat, sprint_id: sprintId }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Couldn't submit");
      }
      setDone(true);
      setDesc("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't submit");
    }
    setBusy(false);
  }

  if (done) {
    return (
      <div className="rounded-xl border border-[#14A800]/30 bg-[#14A800]/5 p-4 text-sm text-[#108A00]">
        ✓ Thanks — your report was logged. The team reviews these and folds the real ones into
        ADAM&apos;s learnings.{" "}
        <button type="button" className="underline" onClick={() => setDone(false)}>
          Report another
        </button>
      </div>
    );
  }

  if (compact && !open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-full border border-[#E0E0E0] px-4 py-2 text-sm transition-colors hover:border-[#14A800] hover:text-[#108A00]"
      >
        ⚑ Report an issue
      </button>
    );
  }

  return (
    <div className="rounded-xl border bg-background p-5 shadow-sm">
      <div className="mb-1 text-sm font-medium">Report an issue</div>
      <p className="mb-3 text-xs text-muted-foreground">
        Something off in a run or the copy? Tell us — it feeds ADAM&apos;s learnings so it
        happens less over time.
      </p>
      <textarea
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        rows={3}
        placeholder="What went wrong? Be specific — which style, what looked off…"
        className="w-full resize-y rounded-lg border border-[#E0E0E0] p-3 text-sm outline-none focus:border-[#14A800]"
      />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="rounded-lg border border-[#E0E0E0] px-3 py-2 text-sm outline-none focus:border-[#14A800]"
        >
          {CATEGORIES.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        {sprintId && (
          <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-xs text-muted-foreground">
            {sprintId}
          </span>
        )}
        <button
          type="button"
          onClick={submit}
          disabled={busy || !desc.trim()}
          className="ml-auto rounded-full bg-[#14A800] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Submitting…" : "Submit report"}
        </button>
      </div>
      {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
    </div>
  );
}
