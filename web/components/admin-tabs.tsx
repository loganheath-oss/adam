import Link from "next/link";

const TABS = [
  { href: "/admin", label: "Reliability", key: "reliability" },
  { href: "/admin/issues", label: "Issues", key: "issues" },
];

export function AdminTabs({ current }: { current: string }) {
  return (
    <div className="mb-6 flex gap-1 border-b">
      {TABS.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          className={`-mb-px border-b-2 px-4 py-2 text-sm transition-colors ${
            current === t.key
              ? "border-[#14A800] font-medium text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </div>
  );
}
