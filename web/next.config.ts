import type { NextConfig } from "next";

// ONE PUBLIC URL (2026-09-29).
//
// ADAM ran as two deployed services with two hostnames, and the split was
// invisible until it bit someone: Adrie took /admin/storage out of the guide,
// opened it on the host she had in her browser, and got a 404 on a route that
// was working fine on the other one.
//
// The Next.js app already carries its own pages plus ~20 /api route handlers
// that proxy the backend, so it is close to complete on its own. What it never
// had were the backend-only surfaces: the Figma plugin download, the ops
// dashboard, the volume endpoints (/admin/storage, /admin/prune) and /health.
// Those genuinely cannot move — the sprint volume is mounted on the `adam`
// service and Next cannot read that disk.
//
// So the fix is one public hostname, not one process. Anything this app does
// not serve falls through to the backend, which keeps running privately.
//
// `fallback` is the correct phase and the reason this is safe: it is evaluated
// only AFTER Next's own pages, /api handlers and dynamic routes have all failed
// to match. It cannot shadow an existing route, so it can add reachable URLs
// but never take one away. `beforeFiles` or `afterFiles` would both be able to
// hijack /sprints/[id].
//
// Being a catch-all also means it covers routes nobody enumerated — the
// /integrations/* webhooks, /sprints/{id}/finals/*, future additions — instead
// of a hand-kept list that silently rots.
const BACKEND =
  process.env.ADAM_API_URL || "https://adam-production-9618.up.railway.app";

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [{ source: "/:path*", destination: `${BACKEND}/:path*` }],
    };
  },
};

export default nextConfig;
