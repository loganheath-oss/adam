// Sample data mirroring the live Sprints page. In production this comes from the
// FastAPI backend (GET /api/sprints) — the Next.js app is a pure client of the
// existing pipeline, so nothing about ADAM's engine changes.
export type Sprint = {
  updated: string;
  id: string;
  driver: string;
  platform: string;
  status: string; // "complete" | "awaiting_gate_2" | ...
};

export const SPRINTS: Sprint[] = [
  { updated: "2026-07 · 16:02", id: "2026-07-meta-9f5e94ca3040", driver: "verify fixes", platform: "Meta", status: "complete" },
  { updated: "2026-07 · 06:34", id: "2026-07-meta-2c347862ae8b", driver: "ALL STYLES test", platform: "Meta", status: "complete" },
  { updated: "2026-07 · 03:08", id: "2026-07-meta-7b9af545b433", driver: "Demo manifest", platform: "Meta", status: "complete" },
  { updated: "2026-07 · 01:43", id: "2026-07-meta-88d27a3b6c47", driver: "Adrie Etherington", platform: "Meta", status: "awaiting_gate_2" },
  { updated: "2026-07 · 21:01", id: "2026-07-meta-9a9962c5de2c", driver: "Adrie Etherington", platform: "Meta", status: "awaiting_gate_6" },
];
