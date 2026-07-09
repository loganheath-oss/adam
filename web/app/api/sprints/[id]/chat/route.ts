import { backend } from "@/lib/backend";

export const dynamic = "force-dynamic";

// Chat history for a sprint (restored on page load).
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { base, key } = backend();
  if (!base || !key) return Response.json({ messages: [] });
  try {
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/chat-history`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!up.ok) return Response.json({ messages: [] });
    return Response.json(await up.json());
  } catch {
    return Response.json({ messages: [] });
  }
}

// Streams the sprint-scoped chat from the backend (same SSE format as Ask ADAM).
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { base, key } = backend();
  const sse = (obj: unknown, status = 200) =>
    new Response(`data: ${JSON.stringify(obj)}\n\n`, {
      status,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  if (!base || !key) return sse({ type: "error", message: "Backend not configured" }, 500);

  const body = await req.text();
  try {
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/chat/stream`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body,
    });
    if (!up.ok || !up.body) return sse({ type: "error", message: `Backend ${up.status}` }, up.status);
    return new Response(up.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (e) {
    return sse({ type: "error", message: e instanceof Error ? e.message : "Request failed" }, 500);
  }
}
