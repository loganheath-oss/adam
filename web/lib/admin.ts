import { apiGet } from "./backend";

// Shapes returned by the backend (db.py reliability_summary / usage_summary).
export type Incident = {
  sprint_id: string;
  ts: string | null;
  user: string | null;
  stage: number | null;
  state: string | null;
  error: string | null;
};

export type Reliability = {
  enabled: boolean;
  error?: string;
  since_days?: number;
  runs_started?: number;
  completed?: number;
  failed?: number;
  clean_rate?: number | null;
  incidents?: Incident[];
};

export type Usage = {
  enabled: boolean;
  error?: string;
  since_days?: number;
  total_events?: number;
  active_users?: number;
  total_cost_usd?: number;
  by_action?: Record<string, number>;
};

export async function getReliability(days = 30): Promise<Reliability | null> {
  return apiGet<Reliability>(`/admin/reliability?days=${days}`);
}

export async function getUsage(days = 30): Promise<Usage | null> {
  return apiGet<Usage>(`/admin/usage?days=${days}`);
}
