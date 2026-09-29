import { backendSession } from "@/lib/admin-session";
export const dynamic = "force-dynamic";

export async function GET() {
  const { base, cookie } = backendSession();
  const r = await fetch(`${base}/admin/dashboard`, {
    headers: { cookie },
    cache: "no-store",
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
