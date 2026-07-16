import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { apiGet } from "@/lib/backend";
import { CopyPicker, type PickerConcept } from "@/components/copy-picker";

export const dynamic = "force-dynamic";

// Copy review = the picking moment. Product rule (2026-07-16): the top options are
// chosen while working with ADAM, BEFORE anything goes to Figma — only selected
// concepts get images, manifest rows, and boards. Picking is open at Gate 3.
export default async function CopyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [data, st] = await Promise.all([
    apiGet<{ ok: boolean; copy_outputs?: { concepts?: PickerConcept[] } }>(`/sprints/${id}/copy`),
    apiGet<{ state?: string }>(`/sprints/${id}/state`),
  ]);
  const concepts = data?.copy_outputs?.concepts ?? [];
  const editable = st?.state === "awaiting_gate_3";

  return (
    <>
      <Link href={`/sprints/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
        ← Sprint
      </Link>
      <h1 className="mb-1 mt-4 text-3xl font-medium tracking-tight">Copy review</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Pick the winners here — only selected concepts continue to images and Figma.
      </p>

      {concepts.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            No copy yet — the pipeline hasn&apos;t reached copy generation.
          </CardContent>
        </Card>
      ) : (
        <CopyPicker sprintId={id} concepts={concepts} editable={editable} />
      )}
    </>
  );
}
