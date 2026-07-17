import { backend } from "@/lib/backend";

// Saves the approved-quotes library to the FastAPI backend (POST /quotes), key server-side.
export async function POST(req: Request) {
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });

  const body = await req.json().catch(() => null);
  const content = body?.content;
  if (typeof content !== "string") {
    return Response.json({ error: "Missing content" }, { status: 400 });
  }

  try {
    const up = await fetch(`${base}/quotes`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!up.ok) {
      const t = await up.text();
      return Response.json({ error: t || `Backend ${up.status}` }, { status: up.status });
    }
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Request failed" }, { status: 500 });
  }
}
