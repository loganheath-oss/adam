import { ReportIssue } from "@/components/report-issue";
import { IssueTriage } from "@/components/issue-triage";
import { getIssues } from "@/lib/admin";

// "Get Help" — everyone-accessible (Ravi, 2026-07-21): the report form + the queue,
// moved out of the admin dashboard so a driver who hits a problem can just report it.
export const dynamic = "force-dynamic";

const CARD = "rounded-xl border bg-background p-5 shadow-sm";
const STATUS_ORDER = ["open", "triaged", "resolved", "learned"];

function Header() {
  return (
    <header className="mb-6">
      <h1 className="text-4xl font-medium tracking-tight">Get help</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
        Something off in a run, or the copy not right? Report it here. The team reviews these and
        folds the real ones into ADAM&apos;s learnings, so it happens less over time.
      </p>
    </header>
  );
}

export default async function HelpPage() {
  const data = await getIssues();

  return (
    <div>
      <Header />

      {/* Report form — the first thing, since that's why most people land here. */}
      <div className="mb-8">
        <ReportIssue />
      </div>

      {(() => {
        if (!data) {
          return <div className={`${CARD} text-sm text-muted-foreground`}>Couldn&apos;t reach the backend.</div>;
        }
        if (!data.enabled || data.error) {
          return (
            <div className={`${CARD} text-sm text-muted-foreground`}>
              {data.error
                ? `Issue query failed: ${data.error}`
                : "Issue tracking is off — DATABASE_URL isn't configured on the backend."}
            </div>
          );
        }

        const counts = data.counts ?? {};
        const issues = data.issues ?? [];
        const now = Date.now();
        const ageDays = (ts: string | null) =>
          ts ? Math.floor((now - new Date(ts).getTime()) / 86_400_000) : 0;
        const stale = issues.filter(
          (i) => (i.status === "open" || i.status === "triaged") && ageDays(i.ts) >= 7,
        );
        const oldestOpen = issues
          .filter((i) => i.status === "open" || i.status === "triaged")
          .reduce((max, i) => Math.max(max, ageDays(i.ts)), 0);

        return (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {STATUS_ORDER.map((st) => (
                <span key={st} className="rounded-full border px-3 py-1 text-xs tabular-nums text-muted-foreground">
                  {st}: <span className="font-semibold text-foreground">{counts[st] ?? 0}</span>
                </span>
              ))}
              {oldestOpen > 0 && (
                <span className="text-xs text-muted-foreground">· oldest open: {oldestOpen}d</span>
              )}
            </div>

            {stale.length > 0 && (
              <div className="mb-6 rounded-lg border border-amber-400/40 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {stale.length} open issue{stale.length === 1 ? "" : "s"}{" "}
                {stale.length === 1 ? "has" : "have"} been waiting 7+ days — triage or resolve so nothing rots
                before September.
              </div>
            )}

            <h2 className="mb-3 text-lg font-medium">Reported issues</h2>
            {issues.length === 0 ? (
              <div className={`${CARD} text-sm text-muted-foreground`}>No issues reported. 🎉</div>
            ) : (
              <div className="space-y-3">
                {issues.map((issue) => (
                  <IssueTriage key={issue.id} issue={issue} />
                ))}
              </div>
            )}
          </>
        );
      })()}
    </div>
  );
}
