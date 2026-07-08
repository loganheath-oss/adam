import type { Sprint } from "./data";
import { SPRINTS as MOCK_SPRINTS } from "./data";

// Runs SERVER-SIDE only (called from a server component). The API key is read
// from a non-public env var, so it never reaches the browser. The Next app is
// just a client of the existing FastAPI pipeline — this reads the same
// /api/sprints the live tool uses.

type ApiSprint = {
  sprint_id: string;
  state?: string;
  state_label?: string;
  driver?: string;
  platform?: string;
  updated_at?: string;
};

function fmtUpdated(ts?: string): string {
  if (!ts) return "";
  const m = ts.match(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} · ${m[2]}` : ts;
}

export type SprintsResult = { sprints: Sprint[]; live: boolean };

export async function getSprints(): Promise<SprintsResult> {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;

  // No backend configured (e.g. local dev without env) → fall back to sample data.
  if (!base || !key) {
    return { sprints: MOCK_SPRINTS, live: false };
  }

  try {
    const res = await fetch(`${base}/api/sprints`, {
      headers: { "X-API-Key": key },
      cache: "no-store", // always show the current state
    });
    if (!res.ok) return { sprints: MOCK_SPRINTS, live: false };

    const data = await res.json();
    const list: ApiSprint[] = Array.isArray(data) ? data : (data.sprints ?? []);
    const sprints: Sprint[] = list.map((s) => ({
      updated: fmtUpdated(s.updated_at),
      id: s.sprint_id,
      driver: s.driver ?? "",
      platform: s.platform ?? "Meta",
      status: s.state ?? "",
    }));
    return { sprints, live: true };
  } catch {
    return { sprints: MOCK_SPRINTS, live: false };
  }
}

export type SprintDetail = {
  sprint_id: string;
  state: string;
  state_label?: string;
  driver?: string;
  platform?: string;
  targeting?: string;
  delivery_date?: string;
  updated_at?: string;
  error?: string;
  gate?: { num?: number; label?: string; action?: string } | null;
  summary?: Record<string, unknown> | null;
  token_usage?: {
    input_tokens?: number;
    output_tokens?: number;
    calls?: number;
    estimated_cost_usd?: number;
  } | null;
  outputs?: Record<string, boolean> | null;
  order?: {
    brief?: string;
    targeting?: string;
    delivery_date?: string;
    deliverable?: string;
    batches?: Array<{
      visual_styles?: string[];
      resolutions?: Array<{ size: string; ratio: string }>;
      audience?: string;
    }>;
  } | null;
};

export async function getSprint(id: string): Promise<SprintDetail | null> {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  if (!base || !key) return null;
  try {
    const res = await fetch(`${base}/api/sprints/${encodeURIComponent(id)}`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as SprintDetail;
  } catch {
    return null;
  }
}
