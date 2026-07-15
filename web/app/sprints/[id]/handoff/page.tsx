import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { CopyLink } from "@/components/copy-link";
import { getSprint } from "@/lib/sprints";

export const dynamic = "force-dynamic";

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-2 text-sm last:border-none">
      <span className="text-muted-foreground">{k}</span>
      <span className="max-w-[60%] text-right font-medium">{v || "—"}</span>
    </div>
  );
}

export default async function HandoffPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s = await getSprint(id);
  const order = s?.order ?? {};
  const batches = order.batches ?? [];

  const styles = Array.from(
    new Set(batches.flatMap((b) => b.visual_styles ?? Object.keys(b.style_quantities ?? {}))),
  );
  const formats = Array.from(new Set(batches.map((b) => b.format).filter(Boolean) as string[]));
  const sizes = Array.from(new Set(batches.flatMap((b) => (b.resolutions ?? []).map((r) => r.ratio))));
  const qty = batches.reduce(
    (n, b) => n + (b.quantity ?? Object.values(b.style_quantities ?? {}).reduce((a, x) => a + x, 0)),
    0,
  );
  const sprintPath = `/sprints/${id}`;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-2xl border bg-background p-8 shadow-sm sm:p-10">
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-2xl font-semibold text-primary-foreground">✓</div>
        <h1 className="text-3xl font-medium tracking-tight">Order submitted</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Sprint <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{id}</span> is queued and waiting at Gate 2 (Order + Refs review).
        </p>

        <div className="mt-6 rounded-xl border bg-muted/30 px-5 py-3">
          <Row k="Driver" v={s?.driver ?? ""} />
          <Row k="Platform / Format" v={[s?.platform, formats.join(", ")].filter(Boolean).join(" · ")} />
          <Row k="Targeting" v={order.targeting ?? s?.targeting ?? ""} />
          <Row k="Deliverable" v={order.deliverable ?? ""} />
          <Row k="Quantity" v={qty ? String(qty) : ""} />
          <Row k="Visual styles" v={styles.join(", ")} />
          <Row k="Sizes" v={sizes.join(", ")} />
          <Row k="Delivery date" v={order.delivery_date ?? s?.delivery_date ?? ""} />
        </div>

        <div className="mt-6 rounded-xl border border-blue-200 bg-blue-50/60 px-5 py-4 text-sm text-blue-900">
          <strong className="mb-1 block font-semibold">Next step — hand off to the creative team</strong>
          Copy this request link and drop it in the <strong>#paid-acquisition</strong> Slack channel. The creative team opens it from there and walks the sprint through Gates 2 → 6.
          <CopyLink path={sprintPath} />
        </div>

        <div className="mt-6 flex flex-wrap gap-2.5">
          <Link href="/new" className={buttonVariants({})}>Submit another order</Link>
        </div>
      </div>
    </div>
  );
}
