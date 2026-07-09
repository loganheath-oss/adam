import Link from "next/link";
import { SprintWorkspace } from "@/components/sprint-workspace";
import { getSprint } from "@/lib/sprints";

export const dynamic = "force-dynamic";

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

  const artifacts = Object.entries(s.outputs ?? {}).filter(([, v]) => v).map(([k]) => k);
  const has = (f: string) => artifacts.includes(f);
  const subLinks: [string, string][] = [];
  if (has("copy_outputs.json")) subLinks.push(["Copy review", `/sprints/${s.sprint_id}/copy`]);
  if (has("asset_manifest.csv")) subLinks.push(["Finals", `/sprints/${s.sprint_id}/finals`]);
  subLinks.push(["Log", `/sprints/${s.sprint_id}/log`]);

  return (
    <>
      <Link href="/sprints" className="text-sm text-muted-foreground hover:text-foreground">← Sprints</Link>

      <header className="mb-4 mt-4 flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-xl font-bold tracking-tight">{s.sprint_id}</h1>
        <span className="text-sm text-muted-foreground">
          {[s.driver, s.platform, s.targeting].filter(Boolean).join(" · ")}
        </span>
        <div className="ml-auto flex flex-wrap gap-3 text-sm">
          {subLinks.map(([label, href]) => (
            <Link key={href} href={href} className="text-muted-foreground hover:text-foreground">{label}</Link>
          ))}
        </div>
      </header>

      <SprintWorkspace
        sprintId={s.sprint_id}
        initialState={s.state}
        initialDriver={s.driver ?? ""}
        initialPlatform={s.platform ?? "Meta"}
      />
    </>
  );
}
