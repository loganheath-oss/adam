import { backend } from "@/lib/backend";

// Forwards a fully-built order (multi-batch, same contract as the live form) to
// the FastAPI backend. The API key stays server-side.
export async function POST(req: Request) {
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });

  const order = await req.json().catch(() => null);
  if (!order || typeof order !== "object") {
    return Response.json({ error: "Invalid order" }, { status: 400 });
  }

  try {
    const up = await fetch(`${base}/submit`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: JSON.stringify(order),
    });
    const data = await up.json().catch(() => ({}));
    if (!up.ok) return Response.json({ error: data.error || `Backend ${up.status}` }, { status: up.status });
    return Response.json({ sprint_id: data.sprint_id });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
