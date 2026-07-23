"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";

export type AudienceCopy = {
  creative_headline?: string;
  creative_subhead?: string;
  headline?: string;
  headline_short?: string;
  body_short?: string;
  body_long?: string;
};

export type PickerConcept = {
  concept_id?: string;
  visual_style?: string;
  concept_tag?: string;
  selected?: boolean;
  rank?: number;
  creative_headline?: string;
  creative_subhead?: string;
  headline?: string;
  headline_short?: string;
  cta?: string;
  body_short?: string;
  review_notes?: string;
  targeting_copy?: { Prospecting?: AudienceCopy; Retargeting?: AudienceCopy };
};

// Gate-3 winner picking. The rule: the top options are chosen HERE, while working
// with ADAM — only selected concepts get images, manifest rows, and Figma boards.
export function CopyPicker({
  sprintId,
  concepts,
  editable,
}: {
  sprintId: string;
  concepts: PickerConcept[];
  editable: boolean;
}) {
  const router = useRouter();
  const [sel, setSel] = useState<Record<string, boolean>>(
    Object.fromEntries(concepts.map((c) => [c.concept_id ?? c.concept_tag ?? "", !!c.selected])),
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);

  const key = (c: PickerConcept) => c.concept_id ?? c.concept_tag ?? "";
  const selectedCount = Object.values(sel).filter(Boolean).length;
  const dirty = concepts.some((c) => !!c.selected !== !!sel[key(c)]);

  async function save() {
    setBusy(true);
    setErr("");
    try {
      const selections: Record<string, boolean> = {};
      for (const c of concepts) {
        if (c.concept_id && !!c.selected !== !!sel[c.concept_id]) selections[c.concept_id] = !!sel[c.concept_id];
      }
      const res = await fetch(`/api/sprints/${sprintId}/copy-select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selections }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Save failed");
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
    setBusy(false);
  }

  const byStyle = new Map<string, PickerConcept[]>();
  for (const c of concepts) {
    const k = c.visual_style || "—";
    (byStyle.get(k) ?? byStyle.set(k, []).get(k)!).push(c);
  }

  return (
    <div>
      <div
        className={`sticky top-16 z-10 mb-6 flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 text-sm shadow-sm ${
          editable ? "border-[#14A800]/40 bg-[#F4FAF1]" : "bg-background"
        }`}
      >
        <span>
          <strong className="tabular-nums">{selectedCount}</strong> of {concepts.length} concepts will become ads in
          Figma
        </span>
        {editable ? (
          <>
            <span className="text-muted-foreground">— pick your winners, then Save and approve Gate 3.</span>
            <button
              type="button"
              onClick={save}
              disabled={busy || !dirty || selectedCount === 0}
              className="ml-auto rounded-full bg-[#14A800] px-5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "Saving…" : saved ? "✓ Saved" : "Save picks"}
            </button>
          </>
        ) : (
          <span className="text-muted-foreground">
            — picking is open while the sprint is awaiting Gate 3 (copy review).
          </span>
        )}
        {err && <span className="w-full text-red-600">{err}</span>}
      </div>

      <div className="space-y-8">
        {[...byStyle.entries()].map(([style, list]) => {
          const n = list.filter((c) => sel[key(c)]).length;
          return (
            <div key={style}>
              <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-primary">
                {style} <span className="normal-case text-muted-foreground">· {n} shipping</span>
              </h2>
              <div className="grid gap-3 md:grid-cols-2">
                {list.map((c, i) => {
                  const k = key(c);
                  const on = !!sel[k];
                  return (
                    <Card
                      key={i}
                      onClick={editable ? () => setSel((s) => ({ ...s, [k]: !s[k] })) : undefined}
                      className={`${on ? "border-[#14A800]/60 bg-[#F4FAF1]/40" : "opacity-70"} ${
                        editable ? "cursor-pointer transition-colors hover:border-[#14A800]" : ""
                      }`}
                    >
                      <CardContent className="space-y-2 pt-5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs text-muted-foreground">
                            {c.concept_tag}
                            {typeof c.rank === "number" && c.rank > 0 && ` · rank ${c.rank}`}
                          </span>
                          {editable ? (
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                on ? "bg-[#14A800] text-white" : "border text-muted-foreground"
                              }`}
                            >
                              {on ? "✓ ship" : "skip"}
                            </span>
                          ) : (
                            on && (
                              <span className="rounded-full bg-green-50 px-2.5 py-0.5 text-xs text-green-700">
                                selected
                              </span>
                            )
                          )}
                        </div>
                        {/* On-image (Text on Visual) */}
                        <div className="text-base font-semibold">{c.creative_headline || c.headline || "—"}</div>
                        {c.creative_subhead && <div className="text-sm text-muted-foreground">{c.creative_subhead}</div>}
                        {/* Feed headline — LONG and SHORT */}
                        {(c.headline || c.headline_short) && (
                          <div className="text-xs text-muted-foreground">
                            <span className="font-medium uppercase tracking-wide">Headline</span> {c.headline}
                            {c.headline_short ? <span> · <span className="font-medium uppercase tracking-wide">short</span> {c.headline_short}</span> : null}
                          </div>
                        )}
                        {c.cta && (
                          <div className="text-sm">
                            <span className="text-muted-foreground">CTA:</span> {c.cta}
                          </div>
                        )}
                        {c.body_short && <div className="border-t pt-2 text-xs text-muted-foreground">{c.body_short}</div>}
                        {/* Prospecting + Retargeting — each has its OWN creative + feed copy */}
                        {c.targeting_copy && (c.targeting_copy.Prospecting || c.targeting_copy.Retargeting) && (
                          <div className="mt-2 grid gap-3 border-t pt-2 sm:grid-cols-2">
                            {(["Prospecting", "Retargeting"] as const).map((seg) => {
                              const a = c.targeting_copy?.[seg];
                              if (!a) return null;
                              return (
                                <div key={seg} className="space-y-1">
                                  <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{seg}</div>
                                  {a.creative_headline && <div className="text-sm font-medium">{a.creative_headline}</div>}
                                  {(a.headline || a.headline_short) && (
                                    <div className="text-[11px] text-muted-foreground">
                                      HL {a.headline}{a.headline_short ? ` · short ${a.headline_short}` : ""}
                                    </div>
                                  )}
                                  {a.body_short && <div className="text-[11px] text-muted-foreground">{a.body_short}</div>}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {c.review_notes && (
                          <div className="text-xs italic text-muted-foreground/80">{c.review_notes}</div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
