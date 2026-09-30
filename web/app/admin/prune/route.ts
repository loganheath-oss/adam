import { backendSession } from "@/lib/admin-session";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const { base, cookie } = backendSession();
  const r = await fetch(`${base}/admin/prune`, {
    method: "POST",
    headers: { cookie, "content-type": "application/json" },
    body: await req.text(),
    cache: "no-store",
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}

// Opening /admin/prune in a browser (Adrie's link, 2026-09-29) used to 404 and
// then 405: deleting is a POST, made by the dashboard's "Delete selected…"
// control. Send a visitor to that control instead of an error page.
// Relative Location: behind Railway's proxy req.url can carry the internal host.
export async function GET() {
  return new Response(null, { status: 307, headers: { Location: "/admin/dashboard" } });
}
