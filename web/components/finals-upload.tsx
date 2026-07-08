"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

// Upload assembled finals (images, PDF, video, or a Figma "Export selected" ZIP).
export function FinalsUpload({ sprintId }: { sprintId: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function upload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setMsg("");
    const form = new FormData();
    for (const f of Array.from(files)) form.append("files", f, f.name);
    try {
      const res = await fetch(`/api/sprints/${sprintId}/finals/upload`, { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `Upload failed (${res.status})`);
      const n = Array.isArray(data.stored) ? data.stored.length : 0;
      setMsg(`Uploaded ${n} file${n === 1 ? "" : "s"}`);
      router.refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*,.pdf,.zip,.mp4,.gif,.webp"
        className="hidden"
        onChange={(e) => upload(e.target.files)}
      />
      <Button onClick={() => inputRef.current?.click()} disabled={busy}>
        {busy ? "Uploading…" : "Upload finals"}
      </Button>
      {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
    </div>
  );
}
