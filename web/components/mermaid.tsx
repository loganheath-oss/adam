"use client";

import { useEffect, useRef, useState } from "react";

// Client-side mermaid renderer for ```mermaid fences in the wiki. The library is
// dynamically imported so it only loads on pages that actually have a diagram.
// Diagrams render at natural size (useMaxWidth off) inside a scrollable card —
// wide flowcharts scroll instead of shrinking into unreadable text.
let seq = 0;

export function Mermaid({ chart }: { chart: string }) {
  const [svg, setSvg] = useState("");
  const [failed, setFailed] = useState(false);
  const idRef = useRef(`wiki-mmd-${++seq}`);

  useEffect(() => {
    let alive = true;
    import("mermaid")
      .then(async (mod) => {
        const mermaid = mod.default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          flowchart: { useMaxWidth: false },
          sequence: { useMaxWidth: false },
          themeVariables: {
            primaryColor: "#eef7ea",
            primaryBorderColor: "#14a800",
            primaryTextColor: "#111827",
            lineColor: "#9aa0a6",
            secondaryColor: "#f3f4f6",
            tertiaryColor: "#ffffff",
            fontFamily: "-apple-system,Segoe UI,sans-serif",
            fontSize: "14px",
          },
        });
        const { svg } = await mermaid.render(idRef.current, chart);
        if (alive) setSvg(svg);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [chart]);

  if (failed) {
    // Diagram source as a readable fallback rather than nothing.
    return (
      <pre className="my-5 overflow-x-auto rounded-xl border bg-muted/30 p-4 font-mono text-xs leading-relaxed text-muted-foreground">
        {chart}
      </pre>
    );
  }
  if (!svg) {
    return (
      <div className="my-5 rounded-xl border bg-[#fbfdfb] p-6 text-center text-xs text-muted-foreground">
        Rendering diagram…
      </div>
    );
  }
  return (
    <div
      className="my-5 overflow-x-auto rounded-xl border bg-[#fbfdfb] p-4 text-center [&_svg]:inline-block"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
