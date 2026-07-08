import Link from "next/link";
import { FinalCard } from "@/components/final-card";
import { FinalsUpload } from "@/components/finals-upload";
import { apiGet } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Final = {
  name: string;
  is_image?: boolean;
  review?: { status?: string };
};
type FinalsResp = {
  finals?: Final[];
  summary?: { approved?: number; changes_requested?: number; pending?: number; total?: number };
};

export default async function FinalsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiGet<FinalsResp>(`/sprints/${id}/finals`);
  const finals = data?.finals ?? [];
  const s = data?.summary ?? {};

  return (
    <>
      <Link href={`/sprints/${id}`} className="text-sm text-muted-foreground hover:text-foreground">← Sprint</Link>
      <div className="mb-8 mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Finals review</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {finals.length} finals
            {s.approved != null && (
              <>
                <span className="mx-2 text-border">·</span>
                <span className="text-green-700">{s.approved} approved</span>
                <span className="mx-2 text-border">·</span>
                <span className="text-amber-700">{s.changes_requested ?? 0} changes</span>
                <span className="mx-2 text-border">·</span>
                <span>{s.pending ?? 0} pending</span>
              </>
            )}
          </p>
        </div>
        <FinalsUpload sprintId={id} />
      </div>

      {finals.length === 0 ? (
        <div className="rounded-xl border bg-muted/30 p-8 text-center text-muted-foreground">
          No finals uploaded yet — the assembled assets appear here once the designer uploads them.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {finals.map((f) => (
            <FinalCard
              key={f.name}
              sprintId={id}
              name={f.name}
              imgUrl={`/api/sprints/${id}/finals/${encodeURIComponent(f.name)}/img`}
              isImage={!!f.is_image}
              initialStatus={f.review?.status ?? "pending"}
            />
          ))}
        </div>
      )}
    </>
  );
}
