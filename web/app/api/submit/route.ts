import { NextRequest, NextResponse } from "next/server";

// Builds the pipeline order payload and submits it to the FastAPI backend.
// The API key stays server-side; the browser only sends form values.
export async function POST(req: NextRequest) {
  const base = process.env.ADAM_API_URL;
  const key = process.env.ADAM_API_KEY;
  if (!base || !key) {
    return NextResponse.json({ error: "Backend not configured" }, { status: 500 });
  }

  const b = await req.json().catch(() => ({}));
  const styles: string[] = b.styles ?? [];
  const sizes: Array<{ size: string; ratio: string }> = b.sizes ?? [];
  const quantity: number = b.quantity || 1;

  if (!styles.length || !sizes.length) {
    return NextResponse.json({ error: "Pick at least one style and one size" }, { status: 400 });
  }

  const order = {
    delivery_date: b.deliveryDate,
    driver: b.driver || "Next.js test",
    targeting: b.targeting || "Prospecting",
    deliverable: b.deliverable || "images-copy",
    brief: b.brief || "",
    batches: [
      {
        platform: "Meta",
        format: "Static",
        quantity,
        visual_styles: styles,
        style_quantities: Object.fromEntries(styles.map((s) => [s, quantity])),
        resolutions: sizes,
        carousel: false,
        carousel_slides: null,
      },
    ],
  };

  try {
    const res = await fetch(`${base}/submit`, {
      method: "POST",
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: JSON.stringify(order),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json({ error: data.error || `Backend ${res.status}` }, { status: res.status });
    }
    return NextResponse.json({ sprint_id: data.sprint_id });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Request failed" },
      { status: 500 },
    );
  }
}
