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
