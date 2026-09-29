import crypto from "crypto";

// The backend gates /admin/dashboard on a session cookie whose value is a
// deterministic HMAC of the API key (main.py `_session_token`). Because it is
// derived rather than random, this server can compute it and present it on the
// caller's behalf — no login prompt, no key in the browser.
//
// Logan, 2026-09-29, mid-call: "I don't want to login with the API key. That's
// weird." The rest of /admin (spend, activity, digest, issues, roles) already
// renders with no prompt for exactly this reason — the key lives in the server
// env and never reaches the client. The dashboard was the odd one out.
//
// ⚠️ This makes the dashboard AND the prune control reachable by anyone with the
// link. That was a deliberate call, made knowing the trade: deleting sprints is
// now ungated on a public URL. The two-step confirm in the dashboard UI and the
// refusal to delete a running sprint are the only remaining guards.
export function backendSession(): { base: string; cookie: string } {
  const base = process.env.ADAM_API_URL || "https://adam-production-9618.up.railway.app";
  const key = process.env.ADAM_API_KEY || "";
  const token = crypto.createHmac("sha256", key).update("pipeline-session-v1").digest("hex");
  return { base, cookie: `pipeline_sess=${token}` };
}
