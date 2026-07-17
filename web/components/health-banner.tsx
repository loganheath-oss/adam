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

function Pill({ tone, label }: { tone: string; label: string }) {
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-medium ${TONE[tone] ?? TONE.unknown}`}>
      {label}
    </span>
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
        <a href="/admin/activity?action=error.*&days=1">
          <Pill tone={errTone} label={`${errs} error${errs === 1 ? "" : "s"} · 24h`} />
        </a>
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
