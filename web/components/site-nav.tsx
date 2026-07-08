"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

// The nav is defined ONCE (contrast: duplicated ~23 times in the current main.py).
const NAV_ITEMS = [
  { label: "New Order", href: "/new" },
  { label: "Sprints", href: "/sprints" },
  { label: "Wiki", href: "/wiki" },
  { label: "Ask ADAM", href: "/agent" },
  { label: "Sync Log", href: "/sync-log" },
  { label: "Learnings", href: "/learnings" },
] as const;

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-10 border-b bg-background">
      <div className="mx-auto flex h-16 max-w-6xl items-center px-6">
        <Link href="/" className="flex items-center gap-3">
          <span className="text-xl font-semibold text-primary">upwork</span>
          <span className="h-5 w-px bg-border" />
          <span className="text-sm tracking-[0.18em] text-foreground">
            ADAM<span className="text-primary">.</span>
          </span>
        </Link>
        <div className="ml-auto flex gap-6 text-sm">
          {NAV_ITEMS.map(({ label, href }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "border-b-2 border-transparent pb-[3px] text-muted-foreground transition-colors hover:text-foreground",
                  active && "border-primary font-semibold text-foreground",
                )}
              >
                {label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
