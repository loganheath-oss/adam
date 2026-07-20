import { AdminTabs } from "@/components/admin-tabs";
import { getActivity, type ActivityEvent } from "@/lib/admin";
import { ErrorDiagnose } from "@/components/error-diagnose";

// Server component: the chronological event feed. Built for August — the team sees
// exactly what happened and Logan reconstructs the month in September. Errors
// (error.*) are first-class rows here. Filters ride in the URL (no client JS).
export const dynamic = "force-dynamic";

const CARD = "rounded-xl border bg-background p-5 shadow-sm";

// Human labels for the action codes (superset of the Reliability page's map).
const ACTION_LABELS: Record<string, string> = {
  "order.submitted": "Order submitted",
  "sprint.completed": "Sprint completed",
  "sprint.failed": "Sprint failed",
  "copy.generated": "Copy generated",
  "copy.selected": "Gate-3 picks made",
  "image.generated": "Images generated",
  "assembly.completed": "Figma assembly",
  "gate.approved": "Gate approved",
  "chat.asked": "Chat question",
  "learnings.edited": "Learnings edited",
  "quotes.edited": "Quotes edited",
  "issue.reported": "Issue reported",
  "error.unhandled": "Server error",
  "error.client": "UI crash",
  "deploy.detected": "Deploy",
  "error.diagnosed": "Error diagnosed",
};

function label(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// A dot color per action family — errors/failures red, terminal-good green, the
// rest neutral so the eye lands on what's wrong.
function dotColor(action: string): string {
  if (action.startsWith("error.") || action === "sprint.failed") return "bg-red-500";
  if (action === "sprint.completed" || action === "assembly.completed") return "bg-[#14A800]";
  if (action === "order.submitted") return "bg-blue-500";
  return "bg-muted-foreground/40";
}

function isBad(action: string): boolean {
  return action.startsWith("error.") || action === "sprint.failed";
}

function fmtTs(ts: string | null): { d: string; t: string } {
  if (!ts) return { d: "", t: "" };
  const m = ts.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})/);
  return m ? { d: `${m[2]}/${m[3]}`, t: m[4] } : { d: ts, t: "" };
}

// The one-line "what" per event, pulled from meta. Kept deliberately compact.
function metaSummary(e: ActivityEvent): string {
  const m = e.meta ?? {};
  const s = (k: string) => (m[k] == null ? "" : String(m[k]));
  switch (e.action) {
    case "sprint.failed":
      return [s("stage") && `Gate ${s("stage")}`, s("state"), s("error")].filter(Boolean).join(" · ");
    case "error.unhandled":
      return [s("method"), s("path"), `${s("type")}: ${s("error")}`].filter(Boolean).join(" ");
    case "error.client":
      return [s("path"), s("error")].filter(Boolean).join(" — ");
    case "assembly.completed": {
      const base = s("boards") && `${s("boards")}/${s("total")} boards`;
      const w = Number(m.warnings ?? 0), miss = Number(m.misses ?? 0), sh = Number(m.slot_shortfall ?? 0);
      const flags = [miss && `${miss} miss`, sh && `${sh} unfilled`, w && `${w} warn`].filter(Boolean).join(", ");
      return flags ? `${base} — ⚠ ${flags}` : base;
    }
    case "copy.generated": {
      const c = s("cost_usd");
      return c ? `$${Number(c).toFixed(2)}` : "";
    }
    case "gate.approved":
      return s("gate") && `Gate ${s("gate")}`;
    case "issue.reported":
      return s("category");
    case "copy.selected":
      return s("count") && `${s("count")} selected`;
    case "learnings.edited":
    case "quotes.edited":
      return s("chars") && `${s("chars")} chars`;
    default:
      return "";
  }
}

function Header() {
  return (
    <header className="mb-2">
      <h1 className="text-4xl font-medium tracking-tight">Activity</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Everything that happened, newest first — orders, gates, assemblies, edits, and errors in one
        timeline. This is the record the team reads in the moment and Logan reads in September.
      </p>
    </header>
  );
}

type SP = { days?: string; action?: string; user?: string; sprint?: string; offset?: string };

export default async function ActivityPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const days = Number(sp.days ?? 30);
  const action = sp.action ?? "";
  const user = sp.user ?? "";
  const sprint = sp.sprint ?? "";
  const offset = Math.max(0, Number(sp.offset ?? 0));
  const limit = 100;

  const data = await getActivity({ days, action, user, sprint, offset, limit });

  if (!data || !data.enabled || data.error) {
    return (
      <div>
        <Header />
        <AdminTabs current="activity" />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          {!data
            ? "Couldn’t reach the backend."
            : data.error
              ? `Activity query failed: ${data.error}`
              : "Activity tracking is off — DATABASE_URL isn’t configured on the backend."}
        </div>
      </div>
    );
  }

  const events = data.events ?? [];
  const actions = data.actions ?? [];
  const total = data.total ?? 0;
  const shown = events.length;
  const from = total === 0 ? 0 : offset + 1;
  const to = offset + shown;

  // Build a query string preserving filters, swapping offset (for pagination links).
  const withOffset = (o: number) => {
    const q = new URLSearchParams();
    q.set("days", String(days));
    if (action) q.set("action", action);
    if (user) q.set("user", user);
    if (sprint) q.set("sprint", sprint);
    if (o > 0) q.set("offset", String(o));
    return `/admin/activity?${q.toString()}`;
  };

  const filtered = Boolean(action || user || sprint);

  return (
    <div>
      <Header />
      <AdminTabs current="activity" />

      {/* Filter bar — plain GET form, no client JS. */}
      <form method="get" action="/admin/activity" className={`${CARD} mb-4`}>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Window</span>
            <select name="days" defaultValue={String(days)} className="rounded-md border bg-background px-2 py-1.5">
              <option value="1">Last 24h</option>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Event type</span>
            <select name="action" defaultValue={action} className="rounded-md border bg-background px-2 py-1.5">
              <option value="">All events</option>
              <option value="error.*">⚠ Errors only</option>
              {actions.map((a) => (
                <option key={a} value={a}>{label(a)}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">User</span>
            <input name="user" defaultValue={user} placeholder="email" className="rounded-md border bg-background px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Sprint</span>
            <input name="sprint" defaultValue={sprint} placeholder="sprint id" className="rounded-md border bg-background px-2 py-1.5" />
          </label>
          <button type="submit" className="rounded-md bg-[#14A800] px-4 py-1.5 font-medium text-white">
            Filter
          </button>
          {filtered && (
            <a href={`/admin/activity?days=${days}`} className="px-2 py-1.5 text-muted-foreground hover:text-foreground">
              Clear
            </a>
          )}
        </div>
      </form>

      {/* Count line */}
      <div className="mb-3 flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total === 0 ? "No events" : `Showing ${from}–${to} of ${total}`}
          {filtered && " (filtered)"}
        </span>
        <span className="tabular-nums">Last {days} days</span>
      </div>

      {/* Timeline */}
      <div className="overflow-hidden rounded-xl border shadow-sm">
        {events.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Nothing in this window. 🎉</div>
        ) : (
          <ul className="divide-y">
            {events.map((e) => {
              const { d, t } = fmtTs(e.ts);
              const summary = metaSummary(e);
              const bad = isBad(e.action);
              const degraded = e.action === "assembly.completed" && Boolean((e.meta ?? {}).degraded);
              return (
                <li
                  key={e.id}
                  className={`px-4 py-2.5 text-sm ${
                    bad ? "bg-red-50/60" : degraded ? "bg-amber-50/60" : ""
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="w-12 flex-none whitespace-nowrap pt-0.5 font-mono text-xs tabular-nums text-muted-foreground">
                      {d}
                    </span>
                    <span className="w-10 flex-none whitespace-nowrap pt-0.5 font-mono text-xs tabular-nums text-muted-foreground">
                      {t}
                    </span>
                    <span className={`mt-1.5 h-2 w-2 flex-none rounded-full ${dotColor(e.action)}`} />
                    <span className="flex-none">
                      <span className={`font-medium ${isBad(e.action) ? "text-red-700" : "text-foreground"}`}>
                        {label(e.action)}
                      </span>
                    </span>
                    <span className="min-w-0 flex-1 truncate text-muted-foreground" title={summary}>
                      {summary}
                    </span>
                    {e.user && <span className="flex-none truncate text-xs text-muted-foreground">{e.user}</span>}
                    {e.sprint_id && (
                      <a
                        href={`/sprints/${e.sprint_id}`}
                        className="flex-none font-mono text-xs text-[#14A800] hover:underline"
                        title={e.sprint_id}
                      >
                        {e.sprint_id.slice(-6)}
                      </a>
                    )}
                  </div>
                  {bad && (
                    <div className="pl-[5.5rem]">
                      <ErrorDiagnose
                        eventId={e.id}
                        cached={(e.meta ?? {}).diagnosis as Parameters<typeof ErrorDiagnose>[0]["cached"]}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Pagination */}
      {(offset > 0 || to < total) && (
        <div className="mt-4 flex items-center justify-between text-sm">
          {offset > 0 ? (
            <a href={withOffset(Math.max(0, offset - limit))} className="rounded-md border px-3 py-1.5 hover:bg-muted">
              ← Newer
            </a>
          ) : (
            <span />
          )}
          {to < total ? (
            <a href={withOffset(offset + limit)} className="rounded-md border px-3 py-1.5 hover:bg-muted">
              Older →
            </a>
          ) : (
            <span />
          )}
        </div>
      )}
    </div>
  );
}
