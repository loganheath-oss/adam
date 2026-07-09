"use client";

import { usePathname } from "next/navigation";

// Gentle fade-up on each navigation — the page (and its header) rises ~8px and
// fades in, matching upwork-adam. Keyed on pathname so it re-fires per route.
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="animate-in fade-in-0 slide-in-from-bottom-2 duration-500 ease-out">
      {children}
    </div>
  );
}
