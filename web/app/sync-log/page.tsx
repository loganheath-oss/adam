import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export const dynamic = "force-dynamic";

type Entry = { ts?: string; pusher?: string; sha?: string; status?: string; detail?: string };
type Counts = { total: number; ok: number; errors: number };

async function getSyncLog(): Promise<{ entries: Entry[]; counts: Counts }> {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  const empty = { entries: [], counts: { total: 0, ok: 0, errors: 0 } };
  if (!base || !key) return empty;
  try {
    const res = await fetch(`${base}/api/sync-log?limit=50`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!res.ok) return empty;
    return await res.json();
  } catch {
    return empty;
  }
}

function fmtTs(ts?: string) {
  if (!ts) return "—";
  const m = ts.match(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} · ${m[2]}` : ts;
}

export default async function SyncLogPage() {
  const { entries, counts } = await getSyncLog();

  return (
    <>
      <header className="mb-8">
        <h1 className="text-4xl font-medium tracking-tight">Sync Log</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {counts.total} syncs
          <span className="mx-2 text-border">·</span>
          <span className="text-green-700">{counts.ok} ok</span>
          <span className="mx-2 text-border">·</span>
          <span className="text-red-600">{counts.errors} errors</span>
        </p>
      </header>

      <div className="overflow-hidden rounded-xl border shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="font-mono text-xs uppercase tracking-wider">Time</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Pusher</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">SHA</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Status</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e, i) => {
              const ok = e.status === "ok";
              return (
                <TableRow key={i}>
                  <TableCell className="whitespace-nowrap font-mono text-muted-foreground tabular-nums">{fmtTs(e.ts)}</TableCell>
                  <TableCell className="font-medium">{e.pusher || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{e.sha || "—"}</TableCell>
                  <TableCell>
                    <span
                      className={`rounded-full px-2.5 py-0.5 font-mono text-xs ${
                        ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"
                      }`}
                    >
                      {ok ? "ok" : "error"}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-md truncate font-mono text-xs text-muted-foreground" title={e.detail}>
                    {e.detail || "—"}
                  </TableCell>
                </TableRow>
              );
            })}
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  No syncs recorded yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
