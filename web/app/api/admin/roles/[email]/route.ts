import { backend } from "@/lib/backend";

// Admin role change → forwards to the FastAPI backend PATCH /admin/roles/{email}.
// Key stays server-side.
export async function PATCH(req: Request, { params }: { params: Promise<{ email: string }> }) {
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });

  const { email } = await params;
  const body = await req.json().catch(() => ({}));

  try {
    const up = await fetch(`${base}/admin/roles/${encodeURIComponent(email)}`, {
      method: "PATCH",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await up.json().catch(() => ({}));
    if (!up.ok) return Response.json({ error: j.error || `Backend ${up.status}` }, { status: up.status });
    return Response.json(j);
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
