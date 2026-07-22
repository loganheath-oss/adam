"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { UpworkLogo } from "@/components/upwork-logo";

// Primary nav — the three things every user needs (Ravi, 2026-07-21):
// New Order → Ask ADAM → Wiki. Everything else lives behind the profile menu.
const PRIMARY = [
  { label: "New Order", href: "/new" },
  { label: "Ask ADAM", href: "/agent" },
  { label: "Wiki", href: "/wiki" },
] as const;

// Behind the profile icon. Role-gating (hide the dashboard from non-admins) wires
// in once SSO/identity lands; today the app has no auth so everything is visible.
const MENU = [
  { label: "ADAM Dashboard", href: "/admin" },
  { label: "Sprint runs", href: "/sprints" },
  { label: "Sync Log", href: "/sync-log" },
  { label: "Teach ADAM", href: "/learnings" },
  { label: "Get Help", href: "/help" },
] as const;

function ProfileIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
    </svg>
  );
}

export function SiteNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  // The landing page is a dark hero; the nav sits on it in dark mode.
  const dark = pathname === "/";
  const inMenu = MENU.some((m) => pathname === m.href || pathname.startsWith(m.href + "/"));

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

        <div className="ml-auto flex items-center gap-6 text-sm">
          {PRIMARY.map(({ label, href }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
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

          {/* Profile menu — the rest of the app lives here. */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label="Menu"
              aria-expanded={open}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border transition-colors",
                dark
                  ? cn("border-white/20 text-white/80 hover:bg-white/10 hover:text-white", inMenu && "border-primary text-primary")
                  : cn("border-border text-muted-foreground hover:bg-muted hover:text-foreground", inMenu && "border-primary text-primary"),
              )}
            >
              <ProfileIcon className="h-[18px] w-[18px]" />
            </button>

            {open && (
              <>
                {/* click-outside backdrop */}
                <button
                  type="button"
                  aria-hidden
                  tabIndex={-1}
                  className="fixed inset-0 z-10 cursor-default"
                  onClick={() => setOpen(false)}
                />
                <div className="absolute right-0 z-20 mt-2 w-48 overflow-hidden rounded-xl border border-[#ECECEC] bg-white py-1 text-[#0a0a0a] shadow-[0_4px_16px_rgba(0,0,0,0.12)]">
                  {MENU.map(({ label, href }) => {
                    const active = pathname === href || pathname.startsWith(href + "/");
                    return (
                      <Link
                        key={href}
                        href={href}
                        onClick={() => setOpen(false)}
                        className={cn(
                          "block px-4 py-2 text-sm transition-colors hover:bg-muted",
                          active ? "font-medium text-[#14A800]" : "text-[#0a0a0a]",
                        )}
                      >
                        {label}
                      </Link>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
