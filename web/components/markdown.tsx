import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Mermaid } from "@/components/mermaid";

// Shared markdown renderer for the Wiki and Learnings pages. Styles elements with
// Tailwind and rewrites internal `*.md` links to `/wiki/*` so the wiki cross-links work.
export function MarkdownView({ children }: { children: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: (p) => <h1 className="mt-8 mb-4 text-3xl font-medium tracking-tight first:mt-0" {...p} />,
        h2: (p) => <h2 className="mt-8 mb-3 text-xl font-medium tracking-tight" {...p} />,
        h3: (p) => <h3 className="mt-6 mb-2 text-base font-semibold" {...p} />,
        p: (p) => <p className="my-3 leading-relaxed text-foreground/90" {...p} />,
        ul: (p) => <ul className="my-3 list-disc space-y-1 pl-6" {...p} />,
        ol: (p) => <ol className="my-3 list-decimal space-y-1 pl-6" {...p} />,
        li: (p) => <li className="leading-relaxed" {...p} />,
        a: ({ href, ...p }) => {
          let h = href || "#";
          const m = h.match(/^([\w-]+)\.md$/);
          if (m) h = `/wiki/${m[1]}`;
          return <a href={h} className="text-primary underline underline-offset-2" {...p} />;
        },
        code: ({ className, ...p }) =>
          /language-/.test(className || "") ? (
            <code className={className} {...p} />
          ) : (
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]" {...p} />
          ),
        pre: (p) => {
          // ```mermaid fences render as diagrams, not raw code (they were an
          // unreadable wall of flowchart source before).
          const child = p.children as React.ReactElement<{ className?: string; children?: React.ReactNode }> | undefined;
          const cls = child && typeof child === "object" && "props" in child ? child.props.className || "" : "";
          if (/language-mermaid/.test(cls)) {
            const raw = child && typeof child === "object" && "props" in child ? String(child.props.children ?? "") : "";
            return <Mermaid chart={raw.trim()} />;
          }
          return <pre className="my-5 overflow-x-auto rounded-xl bg-[#181818] p-5 font-mono text-[13px] leading-relaxed text-[#e6e6e6]" {...p} />;
        },
        blockquote: (p) => (
          <blockquote className="my-5 rounded-r-lg border-l-[3px] border-primary bg-[#F4FAF1] px-5 py-4 [&_p]:my-1 [&_p]:text-foreground/80" {...p} />
        ),
        table: (p) => (
          <div className="my-4 overflow-x-auto">
            <table className="w-full text-sm" {...p} />
          </div>
        ),
        th: (p) => <th className="border-b px-3 py-2 text-left font-semibold" {...p} />,
        td: (p) => <td className="border-b px-3 py-2" {...p} />,
        hr: () => <hr className="my-6 border-border" />,
        strong: (p) => <strong className="font-semibold" {...p} />,
      }}
    >
      {children}
    </Markdown>
  );
}
