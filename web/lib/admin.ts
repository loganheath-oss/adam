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

export type Issue = {
  id: number;
  ts: string | null;
  user: string | null;
  sprint_id: string | null;
  category: string | null;
  description: string;
  status: string;
  resolution_note: string | null;
};

export type Issues = {
  enabled: boolean;
  error?: string;
  counts?: Record<string, number>;
  open?: number;
  total?: number;
  issues?: Issue[];
};

export async function getIssues(status?: string): Promise<Issues | null> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiGet<Issues>(`/admin/issues${q}`);
}

export type User = {
  email: string;
  name: string | null;
  role: string;
  tags: string[];
  last_seen_at: string | null;
  created_at: string | null;
};

export type Roles = {
  enabled: boolean;
  error?: string;
  counts?: Record<string, number>;
  users?: User[];
};

export async function getRoles(): Promise<Roles | null> {
  return apiGet<Roles>("/admin/roles");
}

export type ActivityEvent = {
  id: number;
  ts: string | null;
  action: string;
  user: string | null;
  sprint_id: string | null;
  meta: Record<string, unknown>;
};

export type Activity = {
  enabled: boolean;
  error?: string;
  since_days?: number;
  total?: number;
  limit?: number;
  offset?: number;
  returned?: number;
  events?: ActivityEvent[];
  actions?: string[];
};

export async function getActivity(params: {
  days?: number; limit?: number; offset?: number;
  action?: string; user?: string; sprint?: string;
} = {}): Promise<Activity | null> {
  const q = new URLSearchParams();
  q.set("days", String(params.days ?? 30));
  q.set("limit", String(params.limit ?? 100));
  q.set("offset", String(params.offset ?? 0));
  if (params.action) q.set("action", params.action);
  if (params.user) q.set("user", params.user);
  if (params.sprint) q.set("sprint", params.sprint);
  return apiGet<Activity>(`/admin/activity?${q.toString()}`);
}

export type SpendRow = { cost: number; in: number; out: number; runs?: number };
export type Spend = {
  enabled: boolean;
  error?: string;
  since_days?: number;
  total_cost_usd?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  runs?: number;
  by_day?: Array<SpendRow & { day: string }>;
  by_user?: Array<SpendRow & { user: string }>;
  by_model?: Array<SpendRow & { model: string }>;
  month_to_date_usd?: number;
  monthly_budget_usd?: number;
  budget_pct?: number | null;
  projected_month_usd?: number;
};

export async function getSpend(days = 30): Promise<Spend | null> {
  return apiGet<Spend>(`/admin/spend?days=${days}`);
}

export type Health = {
  overall?: "ok" | "warn" | "critical";
  volume?: { used_mb?: number; total_mb?: number; free_mb?: number; pct?: number; status?: string; error?: string };
  anthropic?: { key_present?: boolean; reachable?: boolean; missing_models?: string[]; status?: string; http?: number; error?: string };
  recent_errors_24h?: number | null;
  db?: { connected?: boolean };
};

export async function getHealth(): Promise<Health | null> {
  return apiGet<Health>("/admin/health");
}

export type Digest = {
  enabled: boolean;
  error?: string;
  since_days?: number;
  orders?: number;
  completed?: number;
  failed?: number;
  clean_rate?: number | null;
  incidents?: Incident[];
  assemblies?: number;
  assemblies_degraded?: number;
  gate_approvals?: number;
  picker_uses?: number;
  issues_new?: number;
  issues_open?: number | null;
  errors?: number;
  spend_usd?: number;
  spend_by_user?: Array<{ user: string; cost: number; runs?: number }>;
  month_to_date_usd?: number;
  projected_month_usd?: number;
  monthly_budget_usd?: number;
  runs?: Array<{
    ts?: string | null;
    sprint_id?: string;
    driver?: string;
    platform?: string;
    targeting?: string;
    styles?: string[];
    deliverable?: string;
    assets?: number;
  }>;
  deploys?: Array<{ ts: string | null; sha?: string; message?: string; service?: string }>;
};

export async function getDigest(days = 7): Promise<Digest | null> {
  return apiGet<Digest>(`/admin/digest?days=${days}`);
}
