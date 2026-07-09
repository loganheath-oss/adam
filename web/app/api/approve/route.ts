import { NextRequest, NextResponse } from "next/server";

// Proxies a gate approval to the FastAPI backend, keeping the API key server-side.
export async function POST(req: NextRequest) {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  if (!base || !key) {
    return NextResponse.json({ error: "Backend not configured" }, { status: 500 });
  }

  const { sprintId, gateNum } = await req.json().catch(() => ({}));
  if (!sprintId || gateNum == null) {
    return NextResponse.json({ error: "Missing sprintId or gateNum" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${base}/sprints/${encodeURIComponent(sprintId)}/approve/${gateNum}`,
      {
        method: "POST",
        headers: { "X-API-Key": key, "Content-Type": "application/json" },
        body: "{}",
      },
    );
    const text = await res.text();
    if (!res.ok) {
      return NextResponse.json({ error: text || `Backend ${res.status}` }, { status: res.status });
    }
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Request failed" },
      { status: 500 },
    );
  }
}
