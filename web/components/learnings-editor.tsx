"use client";

import { useState } from "react";
import { MarkdownView } from "@/components/markdown";

const CARD =
  "rounded-2xl border border-[#ECECEC] bg-white shadow-[0_2px_4px_rgba(0,0,0,.04),0_10px_28px_rgba(0,0,0,.07)]";

export function LearningsEditor({ initial }: { initial: string }) {
  const [content, setContent] = useState(initial);
  const [draft, setDraft] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setSaving(true);
    setError("");
    try {
      const res = await fetch("/api/learnings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: draft }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Save failed");
      }
      setContent(draft);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
    setSaving(false);
  }

  return (
    <div>
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight">ADAM Learnings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Guidance shared across every sprint and loaded into Claude&apos;s context on each chat.
          </p>
        </div>
        {!editing && (
          <button
            type="button"
            onClick={() => {
              setDraft(content);
              setError("");
              setEditing(true);
            }}
            className="flex flex-none items-center gap-2 rounded-full border border-[#E0E0E0] px-4 py-2 text-sm transition-colors hover:bg-[#F7F8F6]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
            Edit
          </button>
        )}
      </header>

      {editing ? (
        <div className={`${CARD} p-6`}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={26}
            spellCheck={false}
            className="w-full resize-y rounded-lg border border-[#E0E0E0] p-4 font-mono text-[13px] leading-relaxed outline-none focus:border-[#14A800]"
          />
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          <div className="mt-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setError("");
              }}
              className="rounded-full border border-[#E0E0E0] px-4 py-2 text-sm transition-colors hover:bg-[#F7F8F6]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving || draft === content}
              className="rounded-full bg-[#14A800] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      ) : (
        <div className={`${CARD} p-8`}>
          <MarkdownView>{content}</MarkdownView>
        </div>
      )}
    </div>
  );
}
