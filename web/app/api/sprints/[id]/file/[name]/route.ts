import { backend } from "@/lib/backend";

// Proxies a run artifact (manifest CSV, etc.) for download — key server-side.
export async function GET(_req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  const { id, name } = await params;
  const { base, key } = backend();
  if (!base || !key) return new Response("Backend not configured", { status: 500 });
  try {
    const up = await fetch(
      `${base}/sprints/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`,
      { headers: { "X-API-Key": key } },
    );
    if (!up.ok) return new Response("Not found", { status: up.status });
    const buf = await up.arrayBuffer();
    return new Response(buf, {
      headers: {
        "Content-Type": up.headers.get("content-type") || "application/octet-stream",
        "Content-Disposition": `attachment; filename="${name}"`,
      },
    });
  } catch {
    return new Response("Request failed", { status: 500 });
  }
}
