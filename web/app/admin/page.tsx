import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { AdminHeader } from "@/components/admin-header";
import { HealthBanner } from "@/components/health-banner";
import { getReliability, getUsage, getHealth, getSpend } from "@/lib/admin";

// Server component: fetches the reliability + usage spine from the FastAPI backend
// at request time. The API key stays server-side (see lib/backend.ts).
export const dynamic = "force-dynamic";

const ACTION_LABELS: Record<string, string> = {
  "order.submitted": "Orders submitted",
  "sprint.completed": "Sprints completed",
  "sprint.failed": "Sprints failed",
  "copy.generated": "Copy generated",
  "image.generated": "Images generated",
  "chat.asked": "Chat questions",
  "learnings.edited": "Learnings edited",
  "issue.reported": "Issues reported",
  "assembly.completed": "Figma assemblies",
  "copy.selected": "Gate-3 picks",
};

function pct(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : `${Math.round(n * 1000) / 10}%`;
}

function usd(n: number | null | undefined): string {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}

function rateColor(n: number | null | undefined): string {
  if (n === null || n === undefined) return "text-muted-foreground";
  if (n >= 0.95) return "text-[#14A800]";
  if (n >= 0.85) return "text-amber-600";
  return "text-red-600";
}

function fmtTs(ts: string | null): string {
  if (!ts) return "";
  const m = ts.match(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} · ${m[2]}` : ts;
}

const CARD = "rounded-xl border bg-background p-5 shadow-sm";

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-2 text-3xl font-semibold tabular-nums ${accent ?? ""}`}>{value}</div>
    </div>
  );
}

export default async function AdminPage() {
  const [rel, usage, health, spend] = await Promise.all([
    getReliability(30),
    getUsage(30),
    getHealth(),
    getSpend(30),
  ]);

  // Backend unreachable (no ADAM_API_URL/KEY, or a fetch error).
  if (!rel) {
    return (
      <div>
        <Header />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          Couldn&apos;t reach the backend. Check that <code className="rounded bg-muted px-1">ADAM_API_URL</code> and{" "}
          <code className="rounded bg-muted px-1">ADAM_API_KEY</code> are set for this app.
        </div>
      </div>
    );
  }

  // DB not configured (usage tracking off) or a query error.
  if (!rel.enabled || rel.error) {
    return (
      <div>
        <Header />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          {rel.error
            ? `Usage query failed: ${rel.error}`
            : "Usage tracking is off — DATABASE_URL isn't configured on the backend. Runs still work normally; nothing is being recorded yet."}
        </div>
      </div>
    );
  }

  const runs = rel.runs_started ?? 0;
  const completed = rel.completed ?? 0;
  const failed = rel.failed ?? 0;
  const resolved = completed + failed;
  const incidents = rel.incidents ?? [];

  return (
    <div>
      <Header />

      <HealthBanner health={health} />

      {/* Headline: month-to-date spend — the datapoint the team watches most (Ravi/Logan). */}
      <div className={`${CARD} mb-4`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Spend · month to date
            </div>
            <div className="mt-1 text-6xl font-semibold tabular-nums">{usd(spend?.month_to_date_usd)}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Projected month-end {usd(spend?.projected_month_usd)}
              {spend?.monthly_budget_usd ? ` of ${usd(spend.monthly_budget_usd)} budget` : " · no budget set"}
              {" · "}
              {usd(spend?.total_cost_usd)} in the last 30 days
            </div>
          </div>
          <a href="/admin/spend" className="text-sm font-medium text-[#14A800] hover:underline">
            Spend detail →
          </a>
        </div>
        {/* Budget bar — only when ADAM_MONTHLY_BUDGET_USD is set. */}
        {spend?.monthly_budget_usd ? (
          <div className="mt-5">
            <div className="flex h-2.5 overflow-hidden rounded-full bg-muted">
              <div
                className={
                  (spend.budget_pct ?? 0) > 1
                    ? "bg-red-500"
                    : (spend.budget_pct ?? 0) > 0.8
                      ? "bg-amber-500"
                      : "bg-[#14A800]"
                }
                style={{ width: `${Math.min(100, (spend.budget_pct ?? 0) * 100)}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {Math.round((spend.budget_pct ?? 0) * 100)}% of {usd(spend.monthly_budget_usd)} monthly budget
            </div>
          </div>
        ) : null}
      </div>

      {/* Plain-language reliability verdict — at-a-glance (Ravi). */}
      <div
        className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
          failed > 0
            ? "border-red-400/40 bg-red-50 text-red-700"
            : "border-[#14A800]/30 bg-[#14A800]/5 text-[#108A00]"
        }`}
      >
        {resolved > 0
          ? failed > 0
            ? `${failed} of ${resolved} recent runs failed — see the incidents below.`
            : `All ${completed} finished run${completed === 1 ? "" : "s"} completed clean. Nothing needs attention right now.`
          : "No runs have finished in this window yet — submit an order to see reliability data here."}
      </div>

      {/* Stat row — clean-run rate now lives here (spend is the headline). */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Stat label="Clean-run rate" value={pct(rel.clean_rate)} accent={rateColor(rel.clean_rate)} />
        <Stat label="Runs started" value={String(runs)} />
        <Stat label="Completed" value={String(completed)} accent="text-[#14A800]" />
        <Stat label="Failed" value={String(failed)} accent={failed > 0 ? "text-red-600" : undefined} />
        <Stat label="Active users" value={String(usage?.active_users ?? 0)} />
      </div>

      {/* Incidents */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Incidents</h2>
        <div className="overflow-hidden rounded-xl border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="font-mono text-xs uppercase tracking-wider">When</TableHead>
                <TableHead className="font-mono text-xs uppercase tracking-wider">Sprint</TableHead>
                <TableHead className="font-mono text-xs uppercase tracking-wider">User</TableHead>
                <TableHead className="font-mono text-xs uppercase tracking-wider">Stage</TableHead>
                <TableHead className="font-mono text-xs uppercase tracking-wider">Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {incidents.map((inc, i) => (
                <TableRow key={`${inc.sprint_id}-${i}`}>
                  <TableCell className="whitespace-nowrap font-mono text-muted-foreground tabular-nums">
                    {fmtTs(inc.ts)}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{inc.sprint_id}</TableCell>
                  <TableCell className="whitespace-nowrap">{inc.user ?? "—"}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {inc.stage != null ? `Gate ${inc.stage}` : inc.state === "interrupted" ? "Interrupted" : "—"}
                  </TableCell>
                  <TableCell className="max-w-md truncate text-muted-foreground" title={inc.error ?? ""}>
                    {inc.error ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
              {incidents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                    No incidents in the last {rel.since_days ?? 30} days. 🎉
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Usage breakdown */}
      {usage?.enabled && (
        <div>
          <h2 className="mb-3 text-lg font-medium">
            Usage{" "}
            <span className="text-sm font-normal text-muted-foreground">
              · {usage.total_events ?? 0} events
              {usage.total_cost_usd != null && usage.total_cost_usd > 0 && ` · $${usage.total_cost_usd.toFixed(2)} spend`}
            </span>
          </h2>
          <div className={CARD}>
            {Object.keys(usage.by_action ?? {}).length === 0 ? (
              <div className="text-sm text-muted-foreground">No events recorded yet.</div>
            ) : (
              <ul className="space-y-2.5">
                {Object.entries(usage.by_action ?? {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([action, count]) => {
                    const max = Math.max(...Object.values(usage.by_action ?? { x: 1 }));
                    return (
                      <li key={action} className="flex items-center gap-3 text-sm">
                        <span className="w-44 flex-none text-muted-foreground">
                          {ACTION_LABELS[action] ?? action}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                          <div className="h-full bg-[#14A800]/70" style={{ width: `${(count / max) * 100}%` }} />
                        </div>
                        <span className="w-10 flex-none text-right font-medium tabular-nums">{count}</span>
                      </li>
                    );
                  })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <AdminHeader
      current="reliability"
      title="Overview"
      description="Spend, reliability, and activity at a glance — the health of the tool in one screen."
      right={<span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">Last 30 days</span>}
    />
  );
}
