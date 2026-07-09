import Link from "next/link";
import { WIKI_PAGES } from "@/lib/wiki";
import { MarkdownView } from "@/components/markdown";
import { cn } from "@/lib/utils";

export function WikiLayout({ current, md }: { current: string; md: string }) {
  return (
    <>
      <h1 className="text-4xl font-medium tracking-tight text-[#0a0a0a]">Wiki</h1>
      <p className="mb-8 mt-3 text-muted-foreground">
        The single source of truth for understanding, running, operating, and inheriting ADAM.
      </p>
      <div className="grid gap-8 md:grid-cols-[220px_1fr]">
        <aside className="md:sticky md:top-24 md:self-start">
          <div className="mb-3 font-mono text-xs uppercase tracking-widest text-muted-foreground">ADAM Wiki</div>
          <nav className="flex flex-col gap-0.5 text-sm">
            {WIKI_PAGES.map(([slug, label]) => (
              <Link
                key={slug}
                href={slug === "README" ? "/wiki" : `/wiki/${slug}`}
                className={cn(
                  "rounded-md px-3 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground",
                  slug === current && "bg-primary font-medium text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
        </aside>
        <article className="min-w-0 rounded-2xl border border-[#ECECEC] bg-white p-8 shadow-[0_1px_2px_rgba(0,0,0,.04),0_4px_12px_rgba(0,0,0,.05)]">
          <MarkdownView>{md}</MarkdownView>
        </article>
      </div>
    </>
  );
}
