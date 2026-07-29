#!/usr/bin/env python3
"""ADAM copy-engine regression suite.

Consolidates the ad-hoc verification harnesses from the 2026-07 quality work into a
committed, repeatable gate. Run BEFORE deploying pipeline/prompt/model changes.

Modes:
  python3 tests/copy_regression.py                 # offline: deterministic checks, free, no API
  python3 tests/copy_regression.py --live          # + real copy run, 6 styles (~$0.5)
  python3 tests/copy_regression.py --live --all    # + real copy run, all 24 styles (~$2-3)

Live mode needs ANTHROPIC_API_KEY in the env (run via `railway run --service adam -- …`
so the service key is injected without ever being printed). RUNS_DIR is always pointed
at a scratch dir — live tests NEVER touch real sprint data.

Exit code 0 = all checks pass; 1 = failures (printed).
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRATCH = Path(tempfile.mkdtemp(prefix="adam_regression_"))
# FORCE the scratch dir (never setdefault): `railway run` injects the service's
# RUNS_DIR=/data/runs, which is unreachable locally — and regression runs must
# never touch real sprint data regardless.
os.environ["RUNS_DIR"] = str(SCRATCH)
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import run_pipeline as rp  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


# All 24 order-form styles (must stay in sync with the /new form).
STYLES_24 = ["Graphic with Text", "Split Screen", "Us vs Them", "Photo with Text",
             "Lifestyle Photo", "Testimonial", "Social Media Profile", "Pie Chart",
             "Hybrid", "Search Results", "Search Bar with Talent Badge", "Text Only",
             "Chat Bubble", "Notification", "Reminder", "Device UI", "Platform UI",
             "Meme", "Sticky Note", "Poll", "Tweet / Post Mockup", "Text with Button",
             "Talent Profile", "Bespoke"]
# Styles allowed to have no style-guide entry (generic rules apply).
NO_GUIDE_OK = {"Search Bar with Talent Badge"}


def offline_checks():
    print("\n== OFFLINE (deterministic) ==")

    # 1. Proper-noun / acronym casing backstop
    cases = [("Shipped by friday, hired monday on upwork", "Shipped by Friday, hired Monday on Upwork"),
             ("Your fractional cmo starts Monday", "Your fractional CMO starts Monday"),
             ("ai talent with real roi", "AI talent with real ROI"),
             ("Post it today. Automate it.", "Post it today. Automate it.")]  # pronoun 'it' untouched
    for a, e in cases:
        got = rp._fix_proper_nouns(a)
        check(f"casing: {a[:34]!r}", got == e, f"got {got!r}")

    # 2. Smart trim: never dangles a comma/stopword, respects cap
    for text, cap in [("Hire the right expert today, and win", 20),
                      ("One sentence. Another sentence entirely.", 18)]:
        got = rp._smart_trim(text, cap)
        check(f"smart_trim cap {cap}", len(got) <= cap + 1 and not got.rstrip().endswith(","),
              f"got {got!r} ({len(got)})")

    # 3. Combined caps (Social columns <=65, Sticky double columns <=136)
    c1 = {"profile_left": "Full-stack developer with 8 years shipping apps",
          "profile_right": "Rated 5 stars across 40+ client projects here"}
    rp._enforce_combined_caps(c1, "Social Media Profile")
    tot = len(c1["profile_left"]) + len(c1["profile_right"])
    check("combined caps: Social <=65", tot <= 65, f"total {tot}")
    c2 = {"left_bullets": ["Post a job in minutes", "Get proposals the same day", "Hire the right pro fast"],
          "right_bullets": ["Weeks of job-board silence", "Slow recruiter back-and-forth", "Roles open for months"]}
    rp._enforce_combined_caps(c2, "Sticky Note")
    tot = sum(len(x) for x in c2["left_bullets"]) + sum(len(x) for x in c2["right_bullets"])
    check("combined caps: Sticky <=136", tot <= 136, f"total {tot}")

    # 4. Audience flatten (nested feed promotion — the Adrie empty-copy bug)
    nested = {"creative_headline": "X", "feed": {"body_short": "B", "headline": "H"}}
    flat = rp._flatten_audience(nested)
    check("flatten: nested feed promoted", flat.get("body_short") == "B" and flat.get("headline") == "H")
    check("flatten: flat passthrough", rp._flatten_audience({"body_short": "B"}).get("body_short") == "B")

    # 5. Near-dup headline detection (diverse top-N selection)
    dup_cases = [("Your new site could be live by Friday", "Your new site is converting by Friday", True),
                 ("Hired by Friday", "Hired by Friday, not next quarter", True),
                 ("Your new site could be live by Friday", "Cut the agency retainer. Keep the results.", False),
                 ("Hire smart", "In control", False),
                 ("Only pay for work you need", "You just found a way to hire for less", False)]
    for a, b, expect in dup_cases:
        check(f"near-dup: {a[:24]!r} vs {b[:24]!r}", rp._headlines_near_dup(a, b) == expect)

    # 6. 50/50 long-body parity math (even global index -> bullet, odd -> paragraph)
    bs, cps = rp._COPY_BATCH_SIZE, rp._CONCEPTS_PER_STYLE
    fmts, pos, seq = [], 0, 0
    while pos < cps:
        cnt = min(bs, cps - pos)
        fmts += ["b" if (seq * bs + j) % 2 == 0 else "p" for j in range(cnt)]
        pos += cnt
        seq += 1
    check("50/50 parity assignment", abs(fmts.count("b") - fmts.count("p")) <= 1, f"{fmts}")

    # 7. Every order-form style resolves (guide entry + caps + subhead flag)
    for s in STYLES_24:
        key, entry = rp._guide_entry_for_style(s)
        ok = entry is not None or s in NO_GUIDE_OK
        check(f"style resolves: {s}", ok, "no guide entry")
        hard, soft = rp._style_caps(s)
        check(f"style caps dict: {s}", isinstance(hard, dict) and isinstance(soft, dict))

    # 8. Intake accepts the canonical 24-style payload
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("intake", str(REPO / "pipeline" / "00_intake.py"))
    intake = ilu.module_from_spec(spec)
    spec.loader.exec_module(intake)
    payload = {"delivery_date": "2026-08-03", "driver": "regression", "targeting": "Prospecting and Retargeting",
               "deliverable": "copy-only", "brief": "x",
               "batches": [{"platform": "Meta", "format": "Static", "visual_styles": list(STYLES_24),
                            "style_quantities": {s: 1 for s in STYLES_24},
                            "resolutions": [{"size": "1440 x 1440", "ratio": "1:1"}],
                            "quantity": 1, "audience": "Both"}]}
    errs = intake.validate_payload(payload)
    check("intake accepts 24-style payload", not errs, str(errs)[:120])

    # 9. Craft bar contains no banned/restricted terms (the "resumes" incident)
    banned = ["resume", "vetted", "staffing", "guarantee", "manage talent", "salary"]
    bar = rp._CRAFT_BAR.lower()
    # allow mentions inside the VOCAB TRAP teaching block (quoted as what NOT to say)
    body = bar.split("vocab trap")[0]
    hits = [t for t in banned if re.search(rf"\b{t}", body)]
    check("craft bar clean of banned terms", not hits, f"found {hits}")

    # 10. Compiled refs present + key sections intact
    refs = json.loads((REPO / "configs" / "refs_context.json").read_text())
    check("refs compiled: copy_instructions", len(refs.get("copy_instructions", "")) > 5000)
    check("refs: long-body format rule present",
          "format is assigned per concept" in refs.get("copy_instructions", "").lower())
    check("refs: proper-noun day rule present",
          "days of the week" in refs.get("copy_instructions", "").lower())


def live_checks(all_styles=False):
    print("\n== LIVE (real copy generation — costs API $) ==")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        check("live: ANTHROPIC_API_KEY present", False, "run via `railway run --service adam -- …`")
        return
    styles = STYLES_24 if all_styles else ["Notification", "Talent Profile", "Tweet / Post Mockup",
                                           "Poll", "Sticky Note", "Chat Bubble"]
    brief = ("Sprint 10 THEME: Outcome Alignment. Highlight specific project outcomes with "
             "freelancers (launch a high-converting site, scale paid ads, chatbot support, "
             "standout brand, workflow automation, sales pipeline). Angle: businesses need to "
             "know what Upwork can do for them. Lean into faster-than-competitors language.")
    payload = {"delivery_date": "2026-08-03", "driver": "regression-live", "targeting": "Prospecting and Retargeting",
               "deliverable": "copy-only", "brief": brief,
               "batches": [{"platform": "Meta", "format": "Static", "visual_styles": list(styles),
                            "style_quantities": {s: 1 for s in styles},
                            "resolutions": [{"size": "1440 x 1440", "ratio": "1:1"}],
                            "quantity": 1, "audience": "Both"}]}
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sid = rp.run_full_pipeline(payload)
        rp.resume_gate_2(sid)
    co = json.loads((Path(os.environ["RUNS_DIR"]) / sid / "copy_outputs.json").read_text())
    cs = co["concepts"]

    def norm(s):
        return re.sub(r"[^a-z0-9]+", "", str(s).lower())

    check("live: no failed styles", not co.get("failed_styles"), str(co.get("failed_styles")))
    for s in styles:
        sel = [c for c in cs if norm(c.get("visual_style")) == norm(s) and c.get("selected")]
        p = sum(1 for c in sel if rp._flatten_audience((c.get("targeting_copy") or {}).get("Prospecting") or {}).get("body_short"))
        r = sum(1 for c in sel if rp._flatten_audience((c.get("targeting_copy") or {}).get("Retargeting") or {}).get("body_short"))
        oc = sum(1 for c in sel if str(c.get("creative_headline") or "").strip())
        hl = sum(1 for c in sel if str(c.get("headline") or "").strip() and str(c.get("headline_short") or "").strip())
        check(f"live spec: {s}", len(sel) >= 2 and p >= 2 and r >= 2 and oc == len(sel) and hl == len(sel),
              f"sel={len(sel)} P={p} R={r} oc={oc} hl={hl}")
        # diverse choices: the selected pair must not be near-dups
        if len(sel) >= 2:
            a, b = (sel[0].get("creative_headline") or "", sel[1].get("creative_headline") or "")
            check(f"live diverse picks: {s}", not rp._headlines_near_dup(a, b), f"{a!r} vs {b!r}")
    bl = [c.get("body_long") for c in cs if c.get("body_long")]
    nb = sum(1 for t in bl if re.search(r"\n\s*([^\w\s]|[-•*])", str(t)))
    check("live: ~50/50 long-body split", bl and 0.35 <= nb / len(bl) <= 0.65, f"{nb}/{len(bl)} bulleted")
    # Bulleted bodies must OPEN with a lead-in sentence, never a bare bullet
    # (Adrie 2026-07-29: "just the bullet points with no copy before it").
    bare = [t for t in bl if re.match(r"\s*[^\w\s]", str(t).strip())]
    check("live: bulleted bodies have a lead-in", not bare,
          f"{len(bare)} start with a bullet: {str(bare[0])[:60]!r}" if bare else "")
    blob = " ".join(json.dumps(c) for c in cs if c.get("selected"))
    lows = re.findall(r"\b(monday|tuesday|wednesday|thursday|friday|cfo|cmo|roi|upwork)\b", blob)
    check("live: casing clean in selected copy", not lows, f"lowercase hits {set(lows)}")
    flagged = sum(1 for c in cs if c.get("legal_flags") and c.get("selected"))
    check("live: no legal-flagged concept selected", flagged == 0, f"{flagged} selected with flags")
    tu = json.loads((Path(os.environ["RUNS_DIR"]) / sid / "token_usage.json").read_text())
    print(f"  (live run cost: ${tu.get('estimated_cost_usd')})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run a real copy generation (costs $)")
    ap.add_argument("--all", action="store_true", help="live mode covers all 24 styles (~$2-3)")
    args = ap.parse_args()
    print(f"ADAM copy regression · scratch={SCRATCH}")
    offline_checks()
    if args.live:
        live_checks(all_styles=args.all)
    print(f"\n{'PASS — all checks green' if not FAILURES else 'FAIL — ' + str(len(FAILURES)) + ' failure(s):'}")
    for f in FAILURES:
        print("  ✗", f)
    sys.exit(1 if FAILURES else 0)
