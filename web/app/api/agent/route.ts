export const dynamic = "force-dynamic";

// Streams the Ask ADAM chat from the FastAPI backend, piping the SSE through so
// the browser gets tokens as they arrive. API key stays server-side.
export async function POST(req: Request) {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  const sse = (obj: unknown, status = 200) =>
    new Response(`data: ${JSON.stringify(obj)}\n\n`, {
      status,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });

  if (!base || !key) return sse({ type: "error", message: "Backend not configured" }, 500);

  const body = await req.text();
  try {
    const upstream = await fetch(`${base}/agent/chat`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body,
    });
    if (!upstream.ok || !upstream.body) {
      return sse({ type: "error", message: `Backend ${upstream.status}` }, upstream.status);
    }
    return new Response(upstream.body, {
      status: 200,
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
