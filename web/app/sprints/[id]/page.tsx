import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/status-badge";
import { GateActions } from "@/components/gate-actions";
import { getSprint } from "@/lib/sprints";

export const dynamic = "force-dynamic";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm">{value || "—"}</div>
    </div>
  );
}

export default async function SprintDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const s = await getSprint(id);

  if (!s) {
    return (
      <>
        <Link href="/sprints" className="text-sm text-muted-foreground hover:text-foreground">← Sprints</Link>
        <h1 className="mt-4 text-2xl font-bold">Sprint unavailable</h1>
        <p className="mt-2 text-muted-foreground">
          Couldn’t load <span className="font-mono">{id}</span> from the backend.
        </p>
      </>
    );
  }

  const order = s.order ?? {};
  const batch = order.batches?.[0] ?? {};
  const summary = (s.summary ?? {}) as Record<string, number | string>;
  const tu = s.token_usage ?? {};
  const artifacts = Object.entries(s.outputs ?? {}).filter(([, v]) => v).map(([k]) => k);
  const awaiting = s.state?.startsWith("awaiting_gate");

  return (
    <>
      <Link href="/sprints" className="text-sm text-muted-foreground hover:text-foreground">← Sprints</Link>

      <header className="mt-4 mb-6 flex flex-wrap items-center gap-4">
        <h1 className="font-mono text-2xl font-bold tracking-tight">{s.sprint_id}</h1>
        <StatusBadge status={s.state} />
      </header>
      <p className="-mt-4 mb-8 text-sm text-muted-foreground">
        {[s.driver, s.platform, s.targeting].filter(Boolean).join(" · ")}
      </p>

      {awaiting && s.gate && (
        <Card className="mb-6 border-amber-200 bg-amber-50/50">
          <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
            <div>
              <div className="font-mono text-xs uppercase tracking-wider text-amber-700">
                Awaiting gate {s.gate.num}
              </div>
              <div className="mt-1 text-base font-semibold">{s.gate.label}</div>
              <div className="text-sm text-muted-foreground">{s.gate.action}</div>
            </div>
            <GateActions sprintId={s.sprint_id} gateNum={s.gate.num ?? 0} />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="grid grid-cols-2 gap-4 pt-6">
            <Field label="Delivery date" value={order.delivery_date ?? s.delivery_date} />
            <Field label="Deliverable" value={order.deliverable} />
            <Field
              label="Styles"
              value={
                batch.visual_styles?.length ? (
                  <div className="flex flex-wrap gap-1">
                    {batch.visual_styles.map((v) => (
                      <Badge key={v} variant="secondary" className="font-normal">{v}</Badge>
                    ))}
                  </div>
                ) : null
              }
            />
            <Field
              label="Sizes"
              value={batch.resolutions?.map((r) => r.ratio).join(", ")}
            />
            <div className="col-span-2">
              <Field label="Brief" value={order.brief ? <span className="whitespace-pre-wrap">{order.brief}</span> : "—"} />
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardContent className="grid grid-cols-3 gap-4 pt-6 text-center">
              <div>
                <div className="text-2xl font-bold tabular-nums">{summary.total_assets ?? "—"}</div>
                <div className="text-xs text-muted-foreground">assets</div>
              </div>
              <div>
                <div className="text-2xl font-bold tabular-nums">{summary.delivered ?? "—"}</div>
                <div className="text-xs text-muted-foreground">delivered</div>
              </div>
              <div>
                <div className="text-2xl font-bold tabular-nums">{summary.pending_assembly ?? "—"}</div>
                <div className="text-xs text-muted-foreground">pending</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex items-center justify-between pt-6 text-sm">
              <span className="text-muted-foreground">Token cost</span>
              <span className="font-mono tabular-nums">
                {tu.estimated_cost_usd != null ? `$${Number(tu.estimated_cost_usd).toFixed(4)}` : "—"}
                {tu.calls != null && <span className="text-muted-foreground"> · {tu.calls} calls</span>}
              </span>
            </CardContent>
          </Card>

          {artifacts.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="mb-2 font-mono text-xs uppercase tracking-wider text-muted-foreground">Artifacts</div>
                <div className="flex flex-wrap gap-1">
                  {artifacts.map((a) => (
                    <Badge key={a} variant="outline" className="font-mono text-xs font-normal">{a}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
