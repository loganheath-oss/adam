#!/usr/bin/env python3
"""Harvest the per-template copy rules from Figma into the template registry.

Every Adtype section in the Figma file ("Paid Acquisition 2026") contains a
well-named `Rules` layer — a spec card whose text reads e.g.:
    Adtype_Testimonial
    Testimonial Copy Max: 100
    Credit Name/Title Max: 51

This script reads those cards straight from the source of truth (Figma) and
writes them verbatim into each adtype's `limits_raw` in
configs/figma_template_registry.json, so copy-gen enforces the ACTUAL caps —
no hand-copying, and new/edited rules sync by re-running this.

Run:  railway run python3 scripts/harvest_figma_rules.py
(needs FIGMA_ACCESS_TOKEN in the environment)
"""
import os, re, json, urllib.request, pathlib

FILE_KEY = "DoDwumxELkuAuKKSP5p00e"
BASE = pathlib.Path(__file__).resolve().parent.parent
REG_PATH = BASE / "configs" / "figma_template_registry.json"


def _fetch_document():
    tok = os.environ["FIGMA_ACCESS_TOKEN"]
    req = urllib.request.Request(
        f"https://api.figma.com/v1/files/{FILE_KEY}",
        headers={"X-Figma-Token": tok},
    )
    return json.load(urllib.request.urlopen(req, timeout=120))["document"]


def _texts_in(node):
    out = []
    def walk(x):
        if x.get("type") == "TEXT":
            out.append(x.get("characters", ""))
        for c in x.get("children", []) or []:
            walk(c)
    walk(node)
    return out


def harvest_rules(document):
    """Return {adtype_key: {label: max_int}} keyed by registry name (no 'Adtype_')."""
    rules = {}
    def walk(n):
        if n.get("type") == "FRAME":
            ts = _texts_in(n)
            joined = " | ".join(ts)
            title = next((t for t in ts if t.strip().startswith("Adtype_")), None)
            if title and "Max:" in joined:
                # registry key = title minus 'Adtype_' prefix, up to first newline/'*'
                key = title.strip()[len("Adtype_"):].split("\n")[0].split("*")[0].strip()
                pairs = re.findall(r"([A-Za-z0-9/&\s]+?)\s*Max:\s*(\d+)", joined)
                bucket = rules.setdefault(key, {})
                for label, num in pairs:
                    bucket[label.strip()] = int(num)
        for c in n.get("children", []) or []:
            walk(c)
    walk(document)
    return rules


def main():
    reg = json.loads(REG_PATH.read_text())
    adtypes = reg.get("adtypes", {})
    rules = harvest_rules(_fetch_document())

    def norm(s):
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    updated, unmatched = [], []
    for key, caps in rules.items():
        # match harvested key to a registry adtype (exact, then normalized)
        match = key if key in adtypes else next(
            (k for k in adtypes if norm(k) == norm(key)), None)
        if not match:
            unmatched.append(key)
            continue
        if adtypes[match].get("limits_raw") != caps:
            adtypes[match]["limits_raw"] = caps
            updated.append(f"{match}: {caps}")

    REG_PATH.write_text(json.dumps(reg, indent=2) + "\n")
    print(f"Harvested {len(rules)} rule cards; updated {len(updated)} adtype(s).")
    for u in updated:
        print("  ✓", u)
    if unmatched:
        print("  ⚠ unmatched harvested keys (no registry adtype):", unmatched)


if __name__ == "__main__":
    main()
