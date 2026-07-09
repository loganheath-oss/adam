import { backend } from "@/lib/backend";

export const dynamic = "force-dynamic";

// Lightweight sprint-state poll for the workspace gates rail + quick-bar.
// Mirrors the backend's public /sprints/{id}/state (key stays server-side).
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { base, key } = backend();
  const empty = { sprint_id: id, state: "", updated_at: "", driver: "", platform: "" };
  if (!base || !key) return Response.json(empty);
  try {
    const up = await fetch(`${base}/sprints/${encodeURIComponent(id)}/state`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!up.ok) return Response.json(empty);
    return Response.json(await up.json());
  } catch {
    return Response.json(empty);
  }
}
