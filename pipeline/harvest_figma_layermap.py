#!/usr/bin/env python3
"""Harvest each Adtype's 1440x1800 template LAYER MAP from Elise's Figma file.

Every template has a different copy structure (Poll has bars + a question, Pie
has four quadrants, Testimonial has quote+author, etc.). This reads the actual
layers so the plugin can fill each one by name and the tool knows which fields
to generate. Re-run when Elise edits:

    FIGMA_ACCESS_TOKEN=... python3 pipeline/harvest_figma_layermap.py

Writes configs/figma_layer_map.json.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

KEY = os.environ.get("FIGMA_FILE_KEY", "DoDwumxELkuAuKKSP5p00e")
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
OUT = Path(__file__).parent.parent / "configs" / "figma_layer_map.json"
if not TOKEN:
    sys.exit("FIGMA_ACCESS_TOKEN not set")


def api(path):
    req = urllib.request.Request("https://api.figma.com/v1/" + path,
                                 headers={"X-Figma-Token": TOKEN})
    for a in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception:
            if a == 2:
                raise
            time.sleep(2)


def walk(n, cb, parent=None):
    cb(n, parent)
    for c in (n.get("children") or []):
        walk(c, cb, n)


def classify(role_by_layer, name, parent_name):
    """Infer a semantic role from Elise's layer name."""
    n = name
    low = name.lower()
    if n == "Copy_Headline" or n == "Notification_Headline_Text":
        return "headline"
    if n == "Copy_Subhead" or n == "Subhead-Text" or n == "TextOnly_Subhead_Text":
        return "subhead"
    if n == "Copy_Body":
        return "body"
    if n in ("Copy_CTA", "CTA", "cta_text"):
        return "cta"
    if n == "Copy_Testimonial":
        return "testimonial_quote"
    if n == "Copy_Author":
        return "author"
    if n == "Copy_Name":
        return "name"
    if n == "Copy_Title":
        return "title"
    if n in ("Copy_Left-Column", "Copy_Right-Column"):
        return "column"
    m = re.match(r"Copy_(TopLeft|TopRight|BottomLeft|BottomRight)$", n)
    if m:
        return "pie_quadrant"
    if re.match(r"Copy_Title\d+$", n):
        return "search_result"
    if re.match(r"Copy_Bullet\d+$", n) or re.match(r"UsVsThem_Bullet\d+$", n):
        return "bullet"
    # Poll: a "Stat Block Text" inside a Stat-Percent-* frame is a percentage;
    # the standalone one is the poll question.
    if n == "Stat Block Text":
        if parent_name and "percent" in parent_name.lower():
            return "poll_percent"
        return "poll_question"
    return None


def main():
    top = api(f"files/{KEY}?depth=1")
    page = next((p["id"] for p in top["document"]["children"]
                 if "meta templates" in p["name"].lower()), None)
    if not page:
        sys.exit("no Meta Templates page")
    kids = api(f"files/{KEY}/nodes?ids={urllib.parse.quote(page)}&depth=1")
    containers = list(kids["nodes"].values())[0]["document"]["children"]

    out = {}
    for cont in containers:
        key = re.sub(r"^ad ?type[:_ ]*", "", cont["name"], flags=re.I).strip(" /:").strip()
        data = api(f"files/{KEY}/nodes?ids={urllib.parse.quote(cont['id'])}")
        doc = list(data["nodes"].values())[0]["document"]
        # primary 1440x1800 template frame
        tmpl = None
        for c in (doc.get("children") or []):
            bb = c.get("absoluteBoundingBox") or {}
            if round(bb.get("width", 0)) == 1440 and 1795 <= round(bb.get("height", 0)) <= 1885 \
               and "rule" not in c["name"].lower():
                tmpl = c
                break
        if not tmpl:
            out[key] = {"template": None, "note": "no 1440x1800 template frame"}
            continue

        roles = {}          # role -> [layer names]
        all_text = []       # every editable text layer name
        images = []         # image placeholder layer names
        bar_fills = []      # poll bar fill rects

        def visit(node, parent):
            nm = node.get("name", "")
            t = node.get("type")
            if t == "TEXT":
                all_text.append(nm)
                r = classify(roles, nm, parent.get("name") if parent else None)
                if r:
                    roles.setdefault(r, []).append(nm)
            if "placeholder" in nm.lower():
                images.append(nm)
            if nm.lower().endswith("-fill") and "percent" in nm.lower():
                bar_fills.append(nm)

        walk(tmpl, visit)
        entry = {"template": tmpl["name"], "roles": {k: sorted(set(v)) for k, v in roles.items()},
                 "images": sorted(set(images)), "bar_fills": sorted(set(bar_fills)),
                 "all_text_layers": sorted(set(all_text))}
        out[key] = entry
        print(f"{key:26} {tmpl['name'][:44]:44} roles={list(roles.keys())}")

    registry = {
        "source": f"Figma {KEY} (ADAM 2026) · Meta Templates · 1440x1800",
        "harvested_at": datetime.now(timezone.utc).isoformat(),
        "adtypes": out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
