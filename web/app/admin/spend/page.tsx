import { AdminHeader } from "@/components/admin-header";
import { getSpend, type Spend } from "@/lib/admin";

// Server component: token + cost analytics. Built for Ravi's ask (2026-07-16) —
// definitive spend data to share, budget context, and the numbers to justify a
// usage-approval bump as Anthropic moves to tiered pricing. This is the screen
// that gets screenshotted into those conversations, so it reads clean.
export const dynamic = "force-dynamic";

const CARD = "rounded-xl border bg-background p-5 shadow-sm";

function usd(n: number | null | undefined): string {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}

function tokens(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function shortModel(m: string): string {
  return m.replace(/^claude-/, "").replace(/-\d{8}$/, "");
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Header({ days }: { days: number }) {
  return (
    <AdminHeader
      current="spend"
      title="Spend"
      description="Approximate token usage and cost — by day, by user, by model. Directional figures for budgeting and usage-approval conversations, not billing."
      right={
        <div className="flex gap-1 text-sm">
          {[7, 30, 90].map((d) => (
            <a
              key={d}
              href={`/admin/spend?days=${d}`}
              className={`rounded-full border px-3 py-1 ${
                d === days ? "border-[#14A800] font-medium text-foreground" : "text-muted-foreground"
              }`}
            >
              {d}d
            </a>
          ))}
        </div>
      }
    />
  );
}

export default async function SpendPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = Number(sp.days ?? 30);
  const data: Spend | null = await getSpend(days);

  if (!data || !data.enabled || data.error) {
    return (
      <div>
        <Header days={days} />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          {!data
            ? "Couldn’t reach the backend."
            : data.error
              ? `Spend query failed: ${data.error}`
              : "Spend tracking is off — DATABASE_URL isn’t configured on the backend."}
        </div>
      </div>
    );
  }

  const byDay = data.by_day ?? [];
  const byUser = data.by_user ?? [];
  const byModel = data.by_model ?? [];
  const maxDay = Math.max(...byDay.map((d) => d.cost), 0.0001);
  const budget = data.monthly_budget_usd ?? 0;
  const pct = data.budget_pct ?? null;
  const overBudget = pct != null && pct >= 100;

  return (
    <div>
      <Header days={days} />

      {/* This-month / budget block — the headline for the budget conversation. */}
      <div className={`${CARD} mb-4`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Month to date
            </div>
            <div className="mt-1 text-5xl font-semibold tabular-nums">{usd(data.month_to_date_usd)}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Projected month-end: <span className="font-medium tabular-nums">{usd(data.projected_month_usd)}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Monthly budget
            </div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">
              {budget ? usd(budget) : "not set"}
            </div>
            {budget === 0 && (
              <div className="mt-1 max-w-[15rem] text-xs text-muted-foreground">
                Set <code className="rounded bg-muted px-1">ADAM_MONTHLY_BUDGET_USD</code> in Railway to track against a cap.
              </div>
            )}
          </div>
        </div>
        {budget > 0 && pct != null && (
          <>
            <div className="mt-5 flex h-2.5 overflow-hidden rounded-full bg-muted">
              <div
                className={overBudget ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-[#14A800]"}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
            <div className={`mt-2 text-sm ${overBudget ? "text-red-600" : "text-muted-foreground"}`}>
              {pct.toFixed(1)}% of budget used this month
              {overBudget && " — over budget"}
            </div>
          </>
        )}
      </div>

      {/* Window totals */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label={`Spend (${days}d)`} value={usd(data.total_cost_usd)} />
        <Stat label="Input tokens" value={tokens(data.total_input_tokens)} />
        <Stat label="Output tokens" value={tokens(data.total_output_tokens)} />
        <Stat label="Runs billed" value={String(data.runs ?? 0)} />
      </div>

      {/* Spend by day */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Spend by day</h2>
        <div className={CARD}>
          {byDay.length === 0 ? (
            <div className="text-sm text-muted-foreground">No billed runs in this window.</div>
          ) : (
            <ul className="space-y-2">
              {byDay.map((d) => (
                <li key={d.day} className="flex items-center gap-3 text-sm">
                  <span className="w-16 flex-none font-mono text-xs tabular-nums text-muted-foreground">
                    {d.day.slice(5)}
                  </span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-[#14A800]/70" style={{ width: `${(d.cost / maxDay) * 100}%` }} />
                  </div>
                  <span className="w-16 flex-none text-right font-medium tabular-nums">{usd(d.cost)}</span>
                  <span className="w-12 flex-none text-right text-xs tabular-nums text-muted-foreground">
                    {d.runs}×
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* By model + by user, side by side on wide screens */}
      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-lg font-medium">By model</h2>
          <div className={`${CARD} overflow-x-auto`}>
            {byModel.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                No per-model data in this window yet — the breakdown fills in as new runs record
                which model spent the tokens. (Runs before token-tracking show totals only.)
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="pb-2 font-medium">Model</th>
                    <th className="pb-2 text-right font-medium">In</th>
                    <th className="pb-2 text-right font-medium">Out</th>
                    <th className="pb-2 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {byModel.map((m) => (
                    <tr key={m.model} className="border-t">
                      <td className="py-1.5 font-mono text-xs">{shortModel(m.model)}</td>
                      <td className="py-1.5 text-right tabular-nums">{tokens(m.in)}</td>
                      <td className="py-1.5 text-right tabular-nums">{tokens(m.out)}</td>
                      <td className="py-1.5 text-right font-medium tabular-nums">{usd(m.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-lg font-medium">By user</h2>
          <div className={`${CARD} overflow-x-auto`}>
            {byUser.length === 0 ? (
              <div className="text-sm text-muted-foreground">No billed runs in this window.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="pb-2 font-medium">User</th>
                    <th className="pb-2 text-right font-medium">Runs</th>
                    <th className="pb-2 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {byUser.map((u) => (
                    <tr key={u.user} className="border-t">
                      <td className="max-w-[12rem] truncate py-1.5" title={u.user}>{u.user}</td>
                      <td className="py-1.5 text-right tabular-nums">{u.runs}</td>
                      <td className="py-1.5 text-right font-medium tabular-nums">{usd(u.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
