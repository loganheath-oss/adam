import type { Health } from "@/lib/admin";

// Health strip on the Overview. Two kinds of item, styled DELIBERATELY differently so
// you can tell function from form (Ravi/Logan): read-only STATUS = a dot + text (never
// button-shaped); an ACTIONABLE item = a bordered chip with a hover + arrow. The errors
// item is only actionable when there's something to look at (errs > 0).
const DOT: Record<string, string> = {
  ok: "bg-[#14A800]",
  warn: "bg-amber-500",
  critical: "bg-red-500",
  unknown: "bg-muted-foreground/40",
};
const STATUS_TEXT: Record<string, string> = {
  ok: "text-muted-foreground",
  warn: "text-amber-700",
  critical: "text-red-700",
  unknown: "text-muted-foreground",
};
const CHIP: Record<string, string> = {
  ok: "border-[#14A800]/40 text-[#14A800] hover:bg-[#14A800]/10",
  warn: "border-amber-400/60 text-amber-700 hover:bg-amber-50",
  critical: "border-red-400/60 text-red-700 hover:bg-red-50",
  unknown: "border-border text-muted-foreground hover:bg-muted",
};

// Read-only status — a dot + label. Not a pill, no border, no hover: reads as a readout.
function StatusReadout({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 flex-none rounded-full ${DOT[tone] ?? DOT.unknown}`} />
      <span className={STATUS_TEXT[tone] ?? STATUS_TEXT.unknown}>{label}</span>
    </span>
  );
}

// Clickable — a bordered button chip with a hover fill + nudging arrow + pointer. The
// one interactive thing, so it can't be mistaken for the status readouts beside it.
function ActionChip({ tone, label, href }: { tone: string; label: string; href: string }) {
  return (
    <a
      href={href}
      title="View details"
      className={`group inline-flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${CHIP[tone] ?? CHIP.unknown}`}
    >
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

  const volLabel = `Volume ${vol.pct != null ? `${vol.pct}%` : "?"}${
    vol.free_mb != null ? ` · ${vol.free_mb}MB free` : ""
  }`;

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
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <StatusReadout tone={vol.status ?? "unknown"} label={volLabel} />
        <StatusReadout tone={api.status ?? "unknown"} label={apiLabel} />
        {errs > 0 ? (
          <ActionChip
            tone={errTone}
            label={`${errs} error${errs === 1 ? "" : "s"} · 24h`}
            href="/admin/activity?action=error.*&days=1"
          />
        ) : (
          <StatusReadout tone="ok" label="0 errors · 24h" />
        )}
      </div>
      {banner && (
        <div
          className={`mt-2 rounded-lg border px-3 py-2 text-sm ${
            health.overall === "critical"
              ? "border-red-400/40 bg-red-50 text-red-700"
              : "border-amber-400/40 bg-amber-50 text-amber-700"
          }`}
        >
          {banner}
        </div>
      )}
    </div>
  );
}
