import Link from "next/link";
import { backend } from "@/lib/backend";

export const dynamic = "force-dynamic";

async function getLog(id: string): Promise<string> {
  const { base, key } = backend();
  if (!base || !key) return "(backend not configured)";
  try {
    const res = await fetch(`${base}/sprints/${encodeURIComponent(id)}/files/pipeline.log`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!res.ok) return "(no log yet)";
    return (await res.text()) || "(empty)";
  } catch {
    return "(couldn’t load the log)";
  }
}

export default async function LogPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const log = await getLog(id);
  return (
    <>
      <Link href={`/sprints/${id}`} className="text-sm text-muted-foreground hover:text-foreground">← Sprint</Link>
      <h1 className="mb-1 mt-4 text-2xl font-bold tracking-tight">Generation log</h1>
      <p className="mb-6 font-mono text-xs text-muted-foreground">{id}</p>
      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-slate-900 p-5 font-mono text-xs leading-relaxed text-slate-200">
        {log}
      </pre>
    </>
  );
}
