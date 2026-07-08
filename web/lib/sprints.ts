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
