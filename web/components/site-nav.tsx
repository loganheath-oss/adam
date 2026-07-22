"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { UpworkLogo } from "@/components/upwork-logo";

// Flat top nav — matches Ravi's reference (upwork-adam): every item visible on
// desktop, a hamburger on mobile. (An earlier profile-dropdown was an over-read of
// the meeting notes; his built reference is the source of truth.)
const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "New Order", href: "/new" },
  { label: "Sprints", href: "/sprints" },
  { label: "Wiki", href: "/wiki" },
  { label: "Ask ADAM", href: "/agent" },
  { label: "Sync Log", href: "/sync-log" },
  { label: "Learnings", href: "/learnings" },
] as const;

export function SiteNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  // The landing page is a dark hero; the nav sits on it in dark mode.
  const dark = pathname === "/";

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");

  // Matches Ravi's reference (upwork-adam) exactly: each item is a padded rounded pill;
  // hover fills that pill with a subtle background AND brings the text to full strength;
  // the active item's underline is an inset green bar (::after), not a full-width border.
  const activeUnderline =
    "after:absolute after:-bottom-px after:left-3 after:right-3 after:h-0.5 after:rounded after:bg-[#14A800] after:content-['']";
  const linkClass = (active: boolean) =>
    cn(
      "relative rounded-md px-3 py-1.5 text-[13.5px] transition-colors",
      dark
        ? active
          ? `text-white hover:bg-white/10 ${activeUnderline}`
          : "text-white/70 hover:bg-white/10 hover:text-white"
        : active
          ? `text-foreground hover:bg-[#f7f8f6] ${activeUnderline}`
          : "text-muted-foreground hover:bg-[#f7f8f6] hover:text-foreground",
    );

  return (
    <nav className={cn("sticky top-0 z-20 print:hidden", dark ? "bg-[#181818]" : "border-b bg-background")}>
      <div className="mx-auto flex h-16 max-w-[1080px] items-center px-6">
        <Link href="/" className="flex items-center gap-[11px]">
          <UpworkLogo className={cn("h-[15px] w-auto", dark ? "text-white" : "text-[#0a0a0a]")} />
          <span className={cn("h-[15px] w-px", dark ? "bg-white/25" : "bg-[#d1d5db]")} />
          <span className={cn("text-[20px] leading-none tracking-[0.2em]", dark ? "text-white" : "text-[#0a0a0a]")}>
            ADAM<span className="font-normal text-primary">.</span>
          </span>
        </Link>

        {/* Desktop: flat nav, every item visible (gap-1 — the pills carry their own px-3) */}
        <div className="ml-auto hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map(({ label, href }) => (
            <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined} className={linkClass(isActive(href))}>
              {label}
            </Link>
          ))}
        </div>

        {/* Mobile: hamburger */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label="Open menu"
          aria-expanded={open}
          className={cn(
            "ml-auto flex h-10 w-10 items-center justify-center rounded-lg transition-colors md:hidden",
            dark ? "text-white hover:bg-white/10" : "text-foreground hover:bg-muted",
          )}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-5 w-5">
            {open ? <path d="M18 6 6 18M6 6l12 12" /> : <path d="M4 6h16M4 12h16M4 18h16" />}
          </svg>
        </button>
      </div>

      {/* Mobile menu panel */}
      {open && (
        <div className={cn("border-t md:hidden", dark ? "border-white/10 bg-[#181818]" : "bg-background")}>
          <div className="mx-auto flex max-w-[1080px] flex-col px-6 py-2">
            {NAV_ITEMS.map(({ label, href }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "py-2.5 text-sm transition-colors",
                  dark
                    ? isActive(href) ? "font-medium text-primary" : "text-white/70 hover:text-white"
                    : isActive(href) ? "font-medium text-primary" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
