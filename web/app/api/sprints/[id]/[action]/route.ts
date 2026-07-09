import { backend } from "@/lib/backend";

const ALLOWED = new Set(["retry", "resume"]);

// Proxies retry/resume actions to the backend (key stays server-side).
export async function POST(_req: Request, { params }: { params: Promise<{ id: string; action: string }> }) {
  const { id, action } = await params;
  if (!ALLOWED.has(action)) {
    return Response.json({ error: `Unknown action: ${action}` }, { status: 400 });
  }
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });
  try {
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/${action}`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: "{}",
    });
    const text = await up.text();
    if (!up.ok) return Response.json({ error: text || `Backend ${up.status}` }, { status: up.status });
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
