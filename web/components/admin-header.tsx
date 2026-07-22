import { AdminTabs } from "@/components/admin-tabs";

// One header for every admin page so the tab row always sits at the same Y — the
// per-page headers used to vary in height (different margins, a "Last 30 days" pill
// vs a day-selector vs nothing, 1- vs 2-line descriptions), which made the tabs
// jump when navigating (Ravi). A reserved min-height keeps it rock-steady.
export function AdminHeader({
  current,
  title,
  description,
  right,
}: {
  current: string;
  title: string;
  description: string;
  right?: React.ReactNode;
}) {
  return (
    <>
      <header className="mb-6 flex min-h-[84px] flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="text-4xl font-medium tracking-tight">{title}</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
        {right && <div className="flex-none pt-1">{right}</div>}
      </header>
      <AdminTabs current={current} />
    </>
  );
}
