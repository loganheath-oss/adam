import { backend } from "@/lib/backend";

// Proxy for the error-diagnosis feature: forwards {event_id, force} to the backend's
// /admin/diagnose (key server-side) and relays the AI cause + fix steps.
export async function POST(req: Request) {
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });

  const body = await req.json().catch(() => null);
  const eventId = body?.event_id;
  if (eventId == null) return Response.json({ error: "Missing event_id" }, { status: 400 });

  try {
    const up = await fetch(`${base}/admin/diagnose`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId, force: Boolean(body?.force) }),
    });
    const data = await up.json().catch(() => ({}));
    return Response.json(data, { status: up.status });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
