import { LearningsEditor } from "@/components/learnings-editor";

export const dynamic = "force-dynamic";

async function getLearnings(): Promise<string> {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  if (!base || !key) return "# Learnings\n\nBackend not configured.";
  try {
    const res = await fetch(`${base}/api/learnings`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!res.ok) return "# Learnings\n\nCouldn’t load learnings from the backend.";
    const data = await res.json();
    return data.content || "# Learnings\n\n(empty)";
  } catch {
    return "# Learnings\n\nCouldn’t reach the backend.";
  }
}

export default async function LearningsPage() {
  const md = await getLearnings();
  return <LearningsEditor initial={md} />;
}
