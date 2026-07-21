import type { Health } from "@/lib/admin";

// Proactive health strip on the Reliability dashboard: three at-a-glance pills
// (volume / API + models / recent errors). Green when fine, amber/red when a
// runbook failure mode is looming — so the team sees it before a run hits it.
const TONE: Record<string, string> = {
  ok: "border-[#14A800]/30 bg-[#14A800]/10 text-[#14A800]",
  warn: "border-amber-400/40 bg-amber-50 text-amber-700",
  critical: "border-red-400/40 bg-red-50 text-red-700",
  unknown: "border-muted bg-muted/40 text-muted-foreground",
};

// A pill is a plain status badge unless it has an `href` — then it renders as a
// link with an affordance (pointer, hover, a nudging arrow) so it's obvious which
// pills are clickable and which are just status. (Ravi: don't make non-clickable
// things look identical to clickable ones.)
function Pill({ tone, label, href }: { tone: string; label: string; href?: string }) {
  const base = `inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium ${TONE[tone] ?? TONE.unknown}`;
  if (!href) return <span className={base}>{label}</span>;
  return (
    <a href={href} title="View details" className={`${base} group cursor-pointer transition hover:brightness-95`}>
      {label}
      <span aria-hidden className="transition-transform group-hover:translate-x-0.5">→</span>
    </a>
  );
}

export function HealthBanner({ health }: { health: Health | null }) {
  if (!health) return null;

  const vol = health.volume ?? {};
  const api = health.anthropic ?? {};
  const errs = health.recent_errors_24h ?? 0;
  const errTone = errs === 0 ? "ok" : errs >= 5 ? "critical" : "warn";

  const apiLabel = !api.key_present
    ? "API key missing"
    : api.missing_models && api.missing_models.length
      ? `Model retired: ${api.missing_models.join(", ")}`
      : api.reachable
        ? "API + models OK"
        : `Anthropic unreachable${api.http ? ` (${api.http})` : ""}`;

  const banner =
    health.overall === "critical"
      ? "Needs attention now — a run will likely fail until this is fixed."
      : health.overall === "warn"
        ? "Heads up — trending toward a failure; worth a look."
        : null;

  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <Pill
          tone={vol.status ?? "unknown"}
          label={`Volume ${vol.pct != null ? `${vol.pct}%` : "?"}${
            vol.free_mb != null ? ` · ${vol.free_mb}MB free` : ""
          }`}
        />
        <Pill tone={api.status ?? "unknown"} label={apiLabel} />
        <Pill
          tone={errTone}
          label={`${errs} error${errs === 1 ? "" : "s"} · 24h`}
          href="/admin/activity?action=error.*&days=1"
        />
      </div>
      {banner && (
        <div
          className={`mt-2 rounded-lg border px-3 py-2 text-sm ${
            health.overall === "critical" ? TONE.critical : TONE.warn
          }`}
        >
          {banner}
        </div>
      )}
    </div>
  );
}
