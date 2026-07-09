import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiGet } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Concept = {
  visual_style?: string;
  concept_tag?: string;
  selected?: boolean;
  creative_headline?: string;
  creative_subhead?: string;
  headline?: string;
  cta?: string;
  body_short?: string;
};

export default async function CopyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiGet<{ ok: boolean; copy_outputs?: { concepts?: Concept[] } }>(`/sprints/${id}/copy`);
  const concepts = data?.copy_outputs?.concepts ?? [];

  const byStyle = new Map<string, Concept[]>();
  for (const c of concepts) {
    const k = c.visual_style || "—";
    (byStyle.get(k) ?? byStyle.set(k, []).get(k)!).push(c);
  }

  return (
    <>
      <Link href={`/sprints/${id}`} className="text-sm text-muted-foreground hover:text-foreground">← Sprint</Link>
      <h1 className="mb-1 mt-4 text-3xl font-medium tracking-tight">Copy review</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        {concepts.length} concepts · {concepts.filter((c) => c.selected).length} selected
      </p>

      {concepts.length === 0 && (
        <Card><CardContent className="pt-6 text-muted-foreground">No copy yet — the pipeline hasn’t reached copy generation.</CardContent></Card>
      )}

      <div className="space-y-8">
        {[...byStyle.entries()].map(([style, list]) => (
          <div key={style}>
            <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-primary">{style}</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {list.map((c, i) => (
                <Card key={i} className={c.selected ? "border-primary/50" : ""}>
                  <CardContent className="space-y-2 pt-5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{c.concept_tag}</span>
                      {c.selected && <Badge className="bg-green-50 font-normal text-green-700 hover:bg-green-50">selected</Badge>}
                    </div>
                    <div className="text-base font-semibold">{c.creative_headline || c.headline || "—"}</div>
                    {c.creative_subhead && <div className="text-sm text-muted-foreground">{c.creative_subhead}</div>}
                    {c.cta && <div className="text-sm"><span className="text-muted-foreground">CTA:</span> {c.cta}</div>}
                    {c.body_short && <div className="border-t pt-2 text-xs text-muted-foreground">{c.body_short}</div>}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
