import { backend } from "@/lib/backend";

// Serves a final image inline (proxied, key server-side).
export async function GET(_req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  const { id, name } = await params;
  const { base, key } = backend();
  if (!base || !key) return new Response("Backend not configured", { status: 500 });
  try {
    const up = await fetch(
      `${base}/sprints/${encodeURIComponent(id)}/finals/${encodeURIComponent(name)}`,
      { headers: { "X-API-Key": key } },
    );
    if (!up.ok) return new Response("Not found", { status: up.status });
    return new Response(await up.arrayBuffer(), {
      headers: {
        "Content-Type": up.headers.get("content-type") || "application/octet-stream",
        "Cache-Control": "private, max-age=60",
      },
    });
  } catch {
    return new Response("Request failed", { status: 500 });
  }
}
