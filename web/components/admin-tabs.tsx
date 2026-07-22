import Link from "next/link";

const IC = "h-4 w-4 flex-none";
const ICONS: Record<string, React.ReactNode> = {
  // gauge
  reliability: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><path d="m12 14 4-4" /><path d="M3.34 19a10 10 0 1 1 17.32 0" /></svg>),
  // activity pulse
  activity: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>),
  // dollar
  spend: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><line x1="12" x2="12" y1="2" y2="22" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>),
  // file-text
  digest: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M16 13H8" /><path d="M16 17H8" /><path d="M10 9H8" /></svg>),
  // alert-triangle
  issues: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>),
  // users
  roles: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={IC}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>),
};

const TABS = [
  { href: "/admin", label: "Reliability", key: "reliability" },
  { href: "/admin/activity", label: "Activity", key: "activity" },
  { href: "/admin/spend", label: "Spend", key: "spend" },
  { href: "/admin/digest", label: "Digest", key: "digest" },
  { href: "/admin/roles", label: "Roles", key: "roles" },
];

export function AdminTabs({ current }: { current: string }) {
  return (
    <div className="mb-6 flex flex-wrap gap-1 border-b">
      {TABS.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-4 py-2 text-sm transition-colors ${
            current === t.key
              ? "border-[#14A800] font-medium text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <span className={current === t.key ? "text-[#14A800]" : ""}>{ICONS[t.key]}</span>
          {t.label}
        </Link>
      ))}
    </div>
  );
}
