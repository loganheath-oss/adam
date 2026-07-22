"use client";

// "Export PDF" — uses the browser's print-to-PDF (no dependency, reliable). The
// print stylesheet (print:hidden on nav/tabs/controls) strips the chrome so the
// output is a clean report to send around (Ravi, 2026-07-21).
export function PrintButton({ label = "Export PDF" }: { label?: string }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm text-muted-foreground transition-colors hover:border-[#14A800] hover:text-foreground print:hidden"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
        <path d="M6 9V2h12v7" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect width="12" height="8" x="6" y="14" />
      </svg>
      {label}
    </button>
  );
}
