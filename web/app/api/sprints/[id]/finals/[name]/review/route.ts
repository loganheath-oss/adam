import { backend } from "@/lib/backend";

// Set a final's review status. Body: { reviewer, status, note? }
export async function POST(req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  const { id, name } = await params;
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });
  const body = await req.text();
  try {
    const up = await fetch(
      `${base}/sprints/${encodeURIComponent(id)}/finals/${encodeURIComponent(name)}/review`,
      { method: "POST", headers: { "X-API-Key": key, "Content-Type": "application/json" }, body },
    );
    const text = await up.text();
    if (!up.ok) return Response.json({ error: text || `Backend ${up.status}` }, { status: up.status });
    return new Response(text, { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
