"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

const STATUS_STYLE: Record<string, string> = {
  approved: "bg-green-50 text-green-700",
  changes_requested: "bg-amber-50 text-amber-700",
  pending: "bg-muted text-muted-foreground",
};

export function FinalCard({
  sprintId,
  name,
  imgUrl,
  isImage,
  initialStatus,
}: {
  sprintId: string;
  name: string;
  imgUrl: string;
  isImage: boolean;
  initialStatus: string;
}) {
  const [status, setStatus] = useState(initialStatus || "pending");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function review(newStatus: string) {
    setBusy(true);
    setNote("");
    try {
      const res = await fetch(`/api/sprints/${sprintId}/finals/${encodeURIComponent(name)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewer: "Reviewer", status: newStatus }),
      });
      if (res.ok) setStatus(newStatus);
      else setNote("Failed");
    } finally {
      setBusy(false);
    }
  }

  async function addComment() {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/sprints/${sprintId}/finals/${encodeURIComponent(name)}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author: "Reviewer", text: comment }),
      });
      if (res.ok) {
        setComment("");
        setNote("Comment added");
      } else setNote("Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border">
      <div className="flex aspect-[4/5] items-center justify-center bg-muted/40">
        {isImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imgUrl} alt={name} className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="font-mono text-xs text-muted-foreground">{name}</span>
        )}
      </div>
      <div className="space-y-3 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-xs text-muted-foreground" title={name}>{name}</span>
          <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] ${STATUS_STYLE[status] ?? STATUS_STYLE.pending}`}>
            {status.replace("_", " ")}
          </span>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => review("approved")} disabled={busy}>Approve</Button>
          <Button size="sm" variant="outline" onClick={() => review("changes_requested")} disabled={busy}>Changes</Button>
        </div>
        <div className="flex gap-2">
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment…"
            className="w-full rounded-md border px-2 py-1 text-xs outline-none focus:border-primary"
          />
          <Button size="sm" variant="outline" onClick={addComment} disabled={busy || !comment.trim()}>Add</Button>
        </div>
        {note && <p className="text-xs text-muted-foreground">{note}</p>}
      </div>
    </div>
  );
}
