import { backend } from "@/lib/backend";

export const dynamic = "force-dynamic";

// Proxies a multipart finals upload to the backend, preserving filenames.
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { base, key } = backend();
  if (!base || !key) return Response.json({ error: "Backend not configured" }, { status: 500 });
  try {
    const inForm = await req.formData();
    const outForm = new FormData();
    for (const [k, v] of inForm.entries()) {
      if (v instanceof File) outForm.append(k, v, v.name);
      else outForm.append(k, v);
    }
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/finals/upload`, {
      method: "POST",
      headers: { "X-API-Key": key }, // do NOT set Content-Type — fetch sets the multipart boundary
      body: outForm,
    });
    const text = await up.text();
    if (!up.ok) return Response.json({ error: text || `Backend ${up.status}` }, { status: up.status });
    return new Response(text, { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Upload failed" }, { status: 500 });
  }
}
