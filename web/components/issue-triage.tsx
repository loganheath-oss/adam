"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Issue } from "@/lib/admin";

const STATUS_STYLE: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  triaged: "bg-blue-100 text-blue-800",
  resolved: "bg-gray-200 text-gray-700",
  learned: "bg-[#14A800]/15 text-[#108A00]",
};

function fmtTs(ts: string | null): string {
  if (!ts) return "";
  const m = ts.match(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} · ${m[2]}` : ts;
}

export function IssueTriage({ issue }: { issue: Issue }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [showLearn, setShowLearn] = useState(false);
  const [learning, setLearning] = useState("");

  async function patch(payload: Record<string, unknown>) {
    setBusy(true);
    setErr("");
    try {
      const res = await fetch(`/api/admin/issues/${issue.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Update failed");
      }
      setShowLearn(false);
      setLearning("");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
    setBusy(false);
  }

  return (
    <div className="rounded-xl border bg-background p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className={`rounded-full px-2 py-0.5 font-medium ${STATUS_STYLE[issue.status] ?? "bg-muted"}`}>
          {issue.status}
        </span>
        {issue.category && <span className="rounded-full bg-muted px-2 py-0.5">{issue.category}</span>}
        <span className="tabular-nums">{fmtTs(issue.ts)}</span>
        {issue.user && <span>· {issue.user}</span>}
        {issue.sprint_id && <span className="font-mono">· {issue.sprint_id}</span>}
      </div>

      <p className="mt-2 text-sm">{issue.description}</p>
      {issue.resolution_note && (
        <p className="mt-1.5 text-xs text-muted-foreground">Note: {issue.resolution_note}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {issue.status !== "triaged" && (
          <button type="button" disabled={busy} onClick={() => patch({ status: "triaged" })}
            className="rounded-full border border-[#E0E0E0] px-3 py-1.5 text-xs transition-colors hover:bg-[#F7F8F6] disabled:opacity-60">
            Mark triaged
          </button>
        )}
        {issue.status !== "resolved" && (
          <button type="button" disabled={busy} onClick={() => patch({ status: "resolved" })}
            className="rounded-full border border-[#E0E0E0] px-3 py-1.5 text-xs transition-colors hover:bg-[#F7F8F6] disabled:opacity-60">
            Mark resolved
          </button>
        )}
        <button type="button" disabled={busy} onClick={() => setShowLearn((v) => !v)}
          className="rounded-full border border-[#14A800] px-3 py-1.5 text-xs text-[#108A00] transition-colors hover:bg-[#14A800]/10 disabled:opacity-60">
          ✦ Distill into a learning
        </button>
      </div>

      {showLearn && (
        <div className="mt-3 rounded-lg border border-[#14A800]/30 bg-[#14A800]/5 p-3">
          <p className="mb-2 text-xs text-muted-foreground">
            Write the guidance ADAM should follow so this stops recurring. It&apos;s appended to
            learnings.md (read on every run + chat), and the issue is marked <em>learned</em>.
          </p>
          <textarea
            value={learning}
            onChange={(e) => setLearning(e.target.value)}
            rows={2}
            placeholder="e.g. For Chat Bubble, write two conversational turns, never a headline + subtext."
            className="w-full resize-y rounded-lg border border-[#E0E0E0] p-2.5 text-sm outline-none focus:border-[#14A800]"
          />
          <div className="mt-2 flex justify-end">
            <button type="button" disabled={busy || !learning.trim()}
              onClick={() => patch({ learning })}
              className="rounded-full bg-[#14A800] px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60">
              {busy ? "Saving…" : "Append learning + mark learned"}
            </button>
          </div>
        </div>
      )}
      {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
    </div>
  );
}
