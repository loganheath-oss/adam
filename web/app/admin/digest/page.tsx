import { AdminHeader } from "@/components/admin-header";
import { PrintButton } from "@/components/print-button";
import { CopyTextButton } from "@/components/copy-text-button";
import { getDigest, type Digest } from "@/lib/admin";

// Server component: the period digest — async catch-up for the team and Logan. The
// automated version of Bree's manual August change log. Renders a visual summary
// plus a plaintext block to paste straight into Slack / the change log.
export const dynamic = "force-dynamic";

const CARD = "rounded-xl border bg-background p-5 shadow-sm";

function usd(n: number | null | undefined): string {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}
function pct(n: number | null | undefined): string {
  return n == null ? "—" : `${Math.round(n * 1000) / 10}%`;
}

// The Slack-pasteable text — plain, scannable, no markdown that renders oddly.
function digestText(d: Digest, days: number): string {
  const L: string[] = [];
  L.push(`ADAM — last ${days} days`);
  L.push("");
  L.push(`Runs: ${d.orders ?? 0} submitted · ${d.completed ?? 0} completed · ${d.failed ?? 0} failed (${pct(d.clean_rate)} clean)`);
  L.push(`Assemblies: ${d.assemblies ?? 0}${d.assemblies_degraded ? ` (${d.assemblies_degraded} degraded — check templates)` : ""}`);
  L.push(`Workflow: ${d.gate_approvals ?? 0} gate approvals · Gate-3 picker used ${d.picker_uses ?? 0}×`);
  L.push(`Issues: ${d.issues_new ?? 0} new · ${d.issues_open ?? 0} still open`);
  if ((d.errors ?? 0) > 0) L.push(`Errors logged: ${d.errors}`);
  L.push(`Spend: ${usd(d.spend_usd)} this period · ${usd(d.month_to_date_usd)} month-to-date · projected ${usd(d.projected_month_usd)}${d.monthly_budget_usd ? ` of ${usd(d.monthly_budget_usd)} budget` : ""}`);
  if (d.incidents && d.incidents.length) {
    L.push("");
    L.push("Incidents:");
    for (const i of d.incidents) {
      L.push(`  - ${i.sprint_id ?? "?"} ${i.stage != null ? `(gate ${i.stage})` : ""}: ${i.error ?? i.state ?? "failed"}`);
    }
  }
  if (d.deploys && d.deploys.length) {
    L.push("");
    L.push(`Deploys: ${d.deploys.length}`);
    for (const dep of d.deploys.slice(0, 6)) {
      L.push(`  - ${dep.sha ?? "?"} ${dep.message ?? ""}`);
    }
  }
  return L.join("\n");
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-2 text-2xl font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

function Header({ days }: { days: number }) {
  return (
    <AdminHeader
      current="digest"
      title="Digest"
      description="Everything that happened this period, in one screen — and a plaintext version to paste into the change log or Slack."
      right={
        <div className="flex items-center gap-3">
          <div className="flex gap-1 text-sm">
            {[7, 14, 30].map((d) => (
              <a
                key={d}
                href={`/admin/digest?days=${d}`}
                className={`rounded-full border px-3 py-1 ${
                  d === days ? "border-[#14A800] font-medium text-foreground" : "text-muted-foreground"
                }`}
              >
                {d}d
              </a>
            ))}
          </div>
          <PrintButton />
        </div>
      }
    />
  );
}

export default async function DigestPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = Number(sp.days ?? 7);
  const d: Digest | null = await getDigest(days);

  if (!d || !d.enabled || d.error) {
    return (
      <div>
        <Header days={days} />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          {!d
            ? "Couldn’t reach the backend."
            : d.error
              ? `Digest query failed: ${d.error}`
              : "Digest is off — DATABASE_URL isn’t configured on the backend."}
        </div>
      </div>
    );
  }

  const text = digestText(d, days);
  const degraded = (d.assemblies_degraded ?? 0) > 0;
  const hasErrors = (d.errors ?? 0) > 0;

  return (
    <div>
      <Header days={days} />

      {/* Stat grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Orders" value={String(d.orders ?? 0)} />
        <Stat label="Completed" value={String(d.completed ?? 0)} tone="text-[#14A800]" />
        <Stat label="Failed" value={String(d.failed ?? 0)} tone={(d.failed ?? 0) > 0 ? "text-red-600" : ""} />
        <Stat
          label="Assemblies"
          value={`${d.assemblies ?? 0}${degraded ? ` · ${d.assemblies_degraded}⚠` : ""}`}
          tone={degraded ? "text-amber-600" : ""}
        />
        <Stat label="Open issues" value={String(d.issues_open ?? 0)} />
        <Stat label="Spend" value={usd(d.spend_usd)} />
      </div>

      {/* Workflow read */}
      <div className="mb-6 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{d.gate_approvals ?? 0}</span> gate approvals ·
        Gate-3 picker used <span className="font-medium text-foreground">{d.picker_uses ?? 0}×</span>
        {(d.completed ?? 0) > 0 && (d.picker_uses ?? 0) === 0 && (
          <span className="text-amber-600"> — team is approving copy without the picker</span>
        )}
      </div>

      {/* Callouts */}
      {(degraded || hasErrors) && (
        <div className="mb-6 space-y-2">
          {degraded && (
            <div className="rounded-lg border border-amber-400/40 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {d.assemblies_degraded} assembly{(d.assemblies_degraded ?? 0) === 1 ? "" : "s"} came out degraded —
              likely a Figma template layer got renamed. Check the{" "}
              <a href="/admin/activity?action=assembly.completed" className="underline">assembly events</a>.
            </div>
          )}
          {hasErrors && (
            <div className="rounded-lg border border-red-400/40 bg-red-50 px-3 py-2 text-sm text-red-700">
              {d.errors} error{d.errors === 1 ? "" : "s"} logged this period —{" "}
              <a href="/admin/activity?action=error.*" className="underline">review them</a>.
            </div>
          )}
        </div>
      )}

      {/* Incidents */}
      {d.incidents && d.incidents.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-lg font-medium">Incidents</h2>
          <div className={CARD}>
            <ul className="space-y-2 text-sm">
              {d.incidents.map((i, idx) => (
                <li key={idx} className="flex gap-3">
                  <span className="font-mono text-xs text-muted-foreground">{i.sprint_id?.slice(-6)}</span>
                  <span className="text-muted-foreground">
                    {i.stage != null ? `Gate ${i.stage} · ` : ""}
                    {i.error ?? i.state ?? "failed"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Deploys */}
      {d.deploys && d.deploys.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-lg font-medium">Deploys ({d.deploys.length})</h2>
          <div className={CARD}>
            <ul className="space-y-1.5 text-sm">
              {d.deploys.map((dep, idx) => (
                <li key={idx} className="flex gap-3">
                  <span className="font-mono text-xs text-muted-foreground">{dep.sha ?? "—"}</span>
                  <span className="min-w-0 flex-1 truncate">{dep.message ?? ""}</span>
                  {dep.service && <span className="text-xs text-muted-foreground">{dep.service}</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Pasteable text */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-medium">Paste-ready summary</h2>
        <CopyTextButton text={text} />
      </div>
      <pre className="overflow-x-auto rounded-xl border bg-muted/30 p-4 text-xs leading-relaxed">
        {text}
      </pre>
    </div>
  );
}
