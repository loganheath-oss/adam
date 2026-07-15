"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RoleToggle({ email, role }: { email: string; role: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isAdmin = role === "admin";

  async function flip() {
    setBusy(true);
    setErr("");
    try {
      const res = await fetch(`/api/admin/roles/${encodeURIComponent(email)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: isAdmin ? "member" : "admin" }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Failed");
      }
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-end gap-2">
      {err && <span className="text-xs text-red-600">{err}</span>}
      <button
        type="button"
        disabled={busy}
        onClick={flip}
        className="rounded-full border border-[#E0E0E0] px-3 py-1 text-xs transition-colors hover:bg-[#F7F8F6] disabled:opacity-60"
      >
        {busy ? "…" : isAdmin ? "Make member" : "Make admin"}
      </button>
    </div>
  );
}
