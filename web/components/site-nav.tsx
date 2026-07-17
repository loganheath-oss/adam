"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { UpworkLogo } from "@/components/upwork-logo";

// The nav is defined ONCE (contrast: duplicated ~23 times in the current main.py).
// "Sprints" (browse-all) is intentionally NOT here: submitters end at the order
// confirmation and share the specific sprint link via Slack; the creative team opens
// that link. /sprints still works by direct URL. It returns as an admin/reviewer-
// gated nav item once RBAC lands (see docs/admin-usage-design.md).
const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "New Order", href: "/new" },
  { label: "Wiki", href: "/wiki" },
  { label: "Ask ADAM", href: "/agent" },
  { label: "Sync Log", href: "/sync-log" },
  { label: "Learnings", href: "/learnings" },
  { label: "Quotes", href: "/quotes" },
] as const;

export function SiteNav() {
  const pathname = usePathname();
  // The landing page is a dark hero; the nav sits on it in dark mode.
  const dark = pathname === "/";
  return (
    <nav className={cn("sticky top-0 z-20", dark ? "bg-[#181818]" : "border-b bg-background")}>
      <div className="mx-auto flex h-16 max-w-[1080px] items-center px-6">
        <Link href="/" className="flex items-center gap-[11px]">
          <UpworkLogo className={cn("h-[15px] w-auto", dark ? "text-white" : "text-[#0a0a0a]")} />
          <span className={cn("h-[15px] w-px", dark ? "bg-white/25" : "bg-[#d1d5db]")} />
          <span className={cn("text-[20px] leading-none tracking-[0.2em]", dark ? "text-white" : "text-[#0a0a0a]")}>
            ADAM<span className="font-normal text-primary">.</span>
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
                  "border-b-2 border-transparent pb-[3px] transition-colors",
                  dark
                    ? active
                      ? "border-primary font-medium text-white"
                      : "text-white/70 hover:text-white"
                    : active
                      ? "border-primary text-foreground"
                      : "text-muted-foreground hover:text-foreground",
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
