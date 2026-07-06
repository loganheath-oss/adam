#!/usr/bin/env python3
"""Pull + total the token usage across every sprint on the live Railway app.

The 'easy way to pull it and share it' from the ADAM standup: hits /api/sprints
(which returns each sprint with its token_usage.json) and prints a per-sprint +
grand-total report of input/output tokens, LLM calls, and estimated $ spend.

Run:  railway run python3 pipeline/token_report.py
(uses PIPELINE_API_KEY from the Railway env; nothing is printed except the report)
Override the host with ADAM_URL if needed.
"""
import os, json, urllib.request, urllib.error

URL = os.environ.get("ADAM_URL", "https://adam-production-9618.up.railway.app").rstrip("/") + "/api/sprints"
KEY = os.environ.get("PIPELINE_API_KEY", "")


def main():
    if not KEY:
        print("PIPELINE_API_KEY not in env — run via `railway run python3 pipeline/token_report.py`")
        return
    req = urllib.request.Request(URL, headers={"X-API-Key": KEY})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=45))
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:200]); return
    sprints = data.get("sprints", [])
    tin = tout = calls = 0
    cost = 0.0
    rows = []
    for s in sprints:
        tok = s.get("token_usage") or {}
        i = tok.get("input_tokens", 0) or 0
        o = tok.get("output_tokens", 0) or 0
        c = tok.get("calls", 0) or 0
        usd = tok.get("estimated_cost_usd", 0) or 0
        tin += i; tout += o; calls += c; cost += usd
        if i or o:
            rows.append((s.get("sprint_id", "?"), i, o, c, usd))
    print(f"Sprints total: {len(sprints)}  |  with token data: {len(rows)}\n")
    print(f"{'sprint':38} {'in':>10} {'out':>9} {'calls':>6} {'~$':>8}")
    for sid, i, o, c, usd in rows:
        print(f"{sid:38} {i:>10,} {o:>9,} {c:>6} {usd:>8.2f}")
    print("-" * 76)
    print(f"{'TOTAL':38} {tin:>10,} {tout:>9,} {calls:>6} {cost:>8.2f}")
    print(f"\nGrand total tokens: {tin + tout:,}  (input {tin:,} + output {tout:,})")
    print(f"Estimated spend: ${cost:,.2f}  over {calls} LLM calls, {len(rows)} sprints")


if __name__ == "__main__":
    main()
