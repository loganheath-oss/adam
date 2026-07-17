// Proxy for frontend crash reports: the global error boundary POSTs here, and we
// forward to the FastAPI backend's /client-error sink (which logs an error.client
// event into the Activity timeline). Keeps the backend URL server-side.
export async function POST(req: Request) {
  const base = process.env.ADAM_API_URL;
  if (!base) return Response.json({ ok: false }, { status: 200 });
  try {
    const body = await req.json();
    await fetch(`${base}/client-error`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    // best-effort — never let error reporting throw
  }
  return Response.json({ ok: true });
}
