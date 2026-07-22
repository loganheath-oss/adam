import Link from "next/link";

// "Teach ADAM" groups the two things the team teaches ADAM: durable Learnings it
// reads on every run, and the Approved Quotes testimonial ads draw from. Quotes is
// no longer a top-nav item (Ravi, 2026-07-21) — it lives here as a tab.
const TABS = [
  { href: "/learnings", label: "Learnings", key: "learnings" },
  { href: "/quotes", label: "Quotes", key: "quotes" },
];

export function TeachAdamTabs({ current }: { current: string }) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-x-1 gap-y-2 border-b">
      <span className="mr-3 font-mono text-xs uppercase tracking-widest text-muted-foreground">Teach ADAM</span>
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
