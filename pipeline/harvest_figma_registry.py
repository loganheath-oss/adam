#!/usr/bin/env python3
"""Harvest the Figma template library into a committed source-of-truth registry.

Elise owns the "Paid Acquisition 2026" Figma file and edits it continuously.
Rather than hardcode template names / layer names / copy limits (which drift
every time she edits — the cause of the lorem-ipsum + "template not found"
bugs), we READ them straight from her file. Re-run this whenever the templates
change:

    FIGMA_ACCESS_TOKEN=... python3 pipeline/harvest_figma_registry.py

Writes configs/figma_template_registry.json. Copy generation reads the per-style
`limits` to stay within the on-creative character maxes; the Figma plugin derives
template/layer lookups from Elise's naming convention (Template_{Adtype}_{WxH},
Copy_Headline/Copy_Subhead/Copy_CTA, *-Image-Placeholder).
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

FILE_KEY = os.environ.get("FIGMA_FILE_KEY", "DoDwumxELkuAuKKSP5p00e")
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
OUT = Path(__file__).parent.parent / "configs" / "figma_template_registry.json"

if not TOKEN:
    sys.exit("FIGMA_ACCESS_TOKEN not set")


def api(path):
    req = urllib.request.Request("https://api.figma.com/v1/" + path,
                                 headers={"X-Figma-Token": TOKEN})
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def walk(n, out):
    out.append(n)
    for c in (n.get("children") or []):
        walk(c, out)


# Parse "<Label> Max: <N>" pairs. Digits separate concatenated fields, so a
# label is letters/space/quotes/slash up to its "Max:" (never crossing a digit).
RULE_RE = re.compile(r'([A-Za-z][A-Za-z /"“”\'‘’]*?)\s*Max\s*:?\s*(\d+)')


def canonical(limits):
    """Best-effort map of Elise's field labels to the copy fields ADAM generates."""
    c = {}
    for label, n in limits.items():
        l = label.lower()
        if "headline" in l and "left" not in l and "right" not in l and "single" not in l:
            c.setdefault("headline", n)
        elif l in ("copy", "testimonial copy"):
            c.setdefault("headline", n)  # copy-led styles use the headline slot
        if l in ("cta", "cta/button", "button"):
            c.setdefault("cta", n)
        if "subhead" in l or l.startswith("stat") or "subhead/stat" in l:
            c.setdefault("subhead", n)
        if "bullet" in l:
            c.setdefault("bullet_total", n)
    return c


def main():
    print("Locating Meta Templates page…")
    top = api(f"files/{FILE_KEY}?depth=1")
    page = None
    for p in top["document"]["children"]:
        if "meta templates" in p["name"].lower():
            page = p["id"]
            break
    if not page:
        sys.exit("Could not find a 'Meta Templates' page")
    kids = api(f"files/{FILE_KEY}/nodes?ids={urllib.parse.quote(page)}&depth=1")
    containers = list(kids["nodes"].values())[0]["document"]["children"]

    adtypes = {}
    for cont in containers:
        raw_name = cont["name"]
        key = re.sub(r"^ad ?type[:_ ]*", "", raw_name, flags=re.I).strip(" /:").strip()
        data = api(f"files/{FILE_KEY}/nodes?ids={urllib.parse.quote(cont['id'])}")
        doc = list(data["nodes"].values())[0]["document"]
        nodes = []
        walk(doc, nodes)
        blob = "\n".join(n.get("characters", "") for n in nodes
                         if n.get("type") == "TEXT" and n.get("characters"))
        blob = blob.replace(" ", "\n").replace(" ", "\n")
        limits = {}
        for m in RULE_RE.finditer(blob):
            lab = m.group(1).strip().strip('"“”').strip()
            if lab:
                limits[lab] = int(m.group(2))
        templates, copy_layers, placeholders = [], set(), set()
        for n in nodes:
            nm = n.get("name", "")
            low = nm.lower()
            if low.startswith("template"):
                bb = n.get("absoluteBoundingBox") or {}
                templates.append({"name": nm, "w": round(bb.get("width", 0)),
                                  "h": round(bb.get("height", 0))})
            if low.startswith("copy_") or nm == "CTA":
                copy_layers.add(nm)
            if "placeholder" in low:
                placeholders.add(nm)
        adtypes[key] = {
            "figma_container": raw_name,
            "copy_rules_v1_complete": "Copy Rules V1 Complete" in blob,
            "labeling_complete": "Labeling Complete" in blob,
            "limits_raw": limits,
            "limits": canonical(limits),
            "sizes": sorted(set(f"{t['w']}x{t['h']}" for t in templates if t["w"])),
            "templates": sorted(set(t["name"] for t in templates)),
            "copy_layers": sorted(copy_layers),
            "image_placeholders": sorted(placeholders),
        }
        print(f"  {key:26} limits={adtypes[key]['limits']} "
              f"sizes={adtypes[key]['sizes']} v1={adtypes[key]['copy_rules_v1_complete']}")

    registry = {
        "source": f"Figma {FILE_KEY} (ADAM 2026) · Meta Templates page",
        "harvested_at": datetime.now(timezone.utc).isoformat(),
        "convention": {
            "template": "Template_{Adtype}_{WxH}",
            "layers": ["Copy_Headline", "Copy_Subhead", "Copy_CTA", "CTA (component)"],
            "images": ["Image-Placeholder", "Left-Image-Placeholder", "Right-Image-Placeholder"],
        },
        "adtypes": adtypes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT} — {len(adtypes)} adtypes")


if __name__ == "__main__":
    main()
