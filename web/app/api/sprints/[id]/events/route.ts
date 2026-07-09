import { backend } from "@/lib/backend";

export const dynamic = "force-dynamic";

// Proxies the pipeline-events SSE stream (live progress) so the browser can
// EventSource it without the API key.
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { base, key } = backend();
  const done = () =>
    new Response('data: {"type":"done"}\n\n', {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  if (!base || !key) return done();
  try {
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/pipeline-events`, {
      headers: { "X-API-Key": key },
    });
    if (!up.ok || !up.body) return done();
    return new Response(up.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return done();
  }
}
