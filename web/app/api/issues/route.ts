import { backend } from "@/lib/backend";

// Public "report an issue" capture → forwards to the FastAPI backend POST /issues.
export async function POST(req: Request) {
  const { base } = backend();
  if (!base) return Response.json({ error: "Backend not configured" }, { status: 500 });

  const body = await req.json().catch(() => null);
  const desc = body?.description;
  if (typeof desc !== "string" || !desc.trim()) {
    return Response.json({ error: "A description is required" }, { status: 400 });
  }

  try {
    const up = await fetch(`${base}/issues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await up.json().catch(() => ({}));
    if (!up.ok) return Response.json({ error: j.error || `Backend ${up.status}` }, { status: up.status });
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
