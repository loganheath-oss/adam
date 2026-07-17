import { QuotesEditor } from "@/components/quotes-editor";

export const dynamic = "force-dynamic";

// Adrie's live quote library (decided 2026-07-16: a static PDF goes stale — this is
// editable in-app, volume-backed, and read by testimonial copy-gen on every run).
async function getQuotes(): Promise<string> {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  if (!base || !key) return "# Approved quotes\n\nBackend not configured.";
  try {
    const res = await fetch(`${base}/api/quotes`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    if (!res.ok) return "# Approved quotes\n\nCouldn’t load quotes from the backend.";
    const data = await res.json();
    return data.content || "# Approved quotes\n\n(empty)";
  } catch {
    return "# Approved quotes\n\nCouldn’t reach the backend.";
  }
}

export default async function QuotesPage() {
  const md = await getQuotes();
  return <QuotesEditor initial={md} />;
}
