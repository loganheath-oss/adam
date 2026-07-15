import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { getReliability, getUsage } from "@/lib/admin";

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
};

function pct(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : `${Math.round(n * 1000) / 10}%`;
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
  const [rel, usage] = await Promise.all([getReliability(30), getUsage(30)]);

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

      {/* Headline: clean-run rate */}
      <div className={`${CARD} mb-4`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Clean-run rate
            </div>
            <div className={`mt-1 text-6xl font-semibold tabular-nums ${rateColor(rel.clean_rate)}`}>
              {pct(rel.clean_rate)}
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {resolved > 0
                ? `${completed} of ${resolved} finished runs completed without an incident`
                : "No runs have finished yet in this window"}
            </div>
          </div>
        </div>
        {/* clean vs failed bar */}
        {resolved > 0 && (
          <div className="mt-5 flex h-2.5 overflow-hidden rounded-full bg-muted">
            <div className="bg-[#14A800]" style={{ width: `${(completed / resolved) * 100}%` }} />
            <div className="bg-red-500" style={{ width: `${(failed / resolved) * 100}%` }} />
          </div>
        )}
      </div>

      {/* Stat row */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
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
            Usage <span className="text-sm font-normal text-muted-foreground">· {usage.total_events ?? 0} events</span>
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
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Reliability</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Are runs completing clean? Clean-run rate, incidents, and usage — from the pipeline&apos;s own event log.
        </p>
      </div>
      <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">Last 30 days</span>
    </header>
  );
}
