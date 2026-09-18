#!/usr/bin/env python3
"""Generate the Figma template punch list, with a clickable link per defect.

Elise asked for this on the Designer guide (2026-09-16): "Are you able to tag me
in Figma where this is occurring?" and, on the missing landscape layers, "This
strikes me as something we should fix, not document."

She is right. Documenting a template defect in a guide is the wrong artifact; a
node list she can click is the right one. Every row below points at a real node.

Run:  railway run python3 scripts/gen_figma_punchlist.py
Writes docs/figma-punchlist.md
"""
import json
import os
import pathlib
import re
import urllib.request
from collections import Counter, defaultdict

FILE_KEY = "DoDwumxELkuAuKKSP5p00e"
FILE_SLUG = "ADAM-2026"
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figma-punchlist.md"


def api(path):
    req = urllib.request.Request("https://api.figma.com/v1/" + path,
                                 headers={"X-Figma-Token": TOKEN, "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=180))


def link(node_id):
    return f"https://www.figma.com/design/{FILE_KEY}/{FILE_SLUG}?node-id={node_id.replace(':', '-')}"


def walk(n):
    yield n
    for c in n.get("children") or []:
        yield from walk(c)


def box(n):
    b = n.get("absoluteBoundingBox") or {}
    return (round(b.get("width", 0)), round(b.get("height", 0))) if b else (0, 0)


def main():
    if not TOKEN:
        raise SystemExit("FIGMA_ACCESS_TOKEN not set (run via: railway run)")

    shallow = api(f"files/{FILE_KEY}?depth=1")
    pages = [(p["name"].strip(), p["id"]) for p in shallow["document"]["children"]]
    full = {}
    for nm, pid in pages:
        full[nm] = api(f"files/{FILE_KEY}/nodes?ids={pid}")["nodes"][pid]["document"]

    L = ["# Figma template punch list",
         "",
         "**Generated from the live ADAM 2026 file.** Re-run",
         "`railway run python3 scripts/gen_figma_punchlist.py` to refresh.",
         "",
         f"File last modified: {shallow.get('lastModified')}",
         "",
         "Every item links straight to the node. These are template fixes, not code:",
         "nothing here needs an engineer.",
         ""]

    # ---- 1. duplicate size frames inside a container -----------------------
    L += ["---", "", "## 1. Duplicate size frames", "",
          "Two frames with the same name AND the same size inside one container. The",
          "plugin takes whichever it reaches first, so if the two ever differ, which one",
          "ships is arbitrary. Delete the one you are not using.", ""]
    dupes = 0
    for pname, root in full.items():
        for cont in walk(root):
            nm = str(cont.get("name", ""))
            if not (nm.startswith("Adtype_") or nm.startswith("Reddit_Adtype_")):
                continue
            seen = defaultdict(list)
            for c in cont.get("children") or []:
                if c.get("type") == "FRAME":
                    seen[(c.get("name"), box(c))].append(c)
            for (cn, bx), group in seen.items():
                if len(group) > 1:
                    dupes += 1
                    L.append(f"- **{nm}** on *{pname}*: {len(group)} frames named `{cn}` at {bx[0]}x{bx[1]}")
                    for g in group:
                        L.append(f"    - [{g['id']}]({link(g['id'])})")
    if not dupes:
        L.append("_None found._")
    L.append("")

    # ---- 2. missing copy layers on one size only ---------------------------
    L += ["---", "", "## 2. A size missing copy layers its sibling has", "",
          "The portrait and landscape versions of the same style should carry the same",
          "`Copy_*` layers. Where they do not, the run half-fills and looks fine until you",
          "check both sizes.", ""]
    found_missing = False
    for pname, root in full.items():
        for cont in walk(root):
            nm = str(cont.get("name", ""))
            if not (nm.startswith("Adtype_") or nm.startswith("Reddit_Adtype_")):
                continue
            # Group by VARIANT FAMILY: the frame name with its size token
            # removed. A Sticky-Note _Single_ legitimately carries different
            # layers than a _Double_, so comparing across variants invents
            # defects. Within one family the sizes should match.
            fam = defaultdict(dict)
            for c in cont.get("children") or []:
                if c.get("type") != "FRAME" or str(c.get("name")) == "Rules":
                    continue
                cname = str(c.get("name"))
                layers = {str(t.get("name")) for t in walk(c)
                          if t.get("type") == "TEXT" and str(t.get("name")).startswith("Copy_")}
                if not (layers or box(c)[0] >= 800):
                    continue
                key = re.sub(r"\d{3,5}\s*[x\u00d7]\s*\d{3,5}", "", cname).strip("_- ")
                fam[key][cname] = (c, layers)
            for key, per in fam.items():
                if len(per) < 2:
                    continue
                union = set().union(*[v[1] for v in per.values()])
                if not union:
                    continue
                for sname, (node, layers) in per.items():
                    missing = union - layers
                    if missing:
                        found_missing = True
                        L.append(f"- **{nm}** / `{sname}` is missing {sorted(missing)}")
                        L.append(f"    - [{node['id']}]({link(node['id'])})")
    if not found_missing:
        L.append("_None found._")
    L.append("")

    # ---- 3. nested Image-Placeholder (the leaf rule) -----------------------
    L += ["---", "", "## 3. Photo slot nested inside another photo slot", "",
          "When a frame named `Image-Placeholder` contains a child with the same name, the",
          "plugin fills the OUTER one and the inner keeps its built-in photo, so the",
          "template's stock image ships on the finished ad. Nothing looks wrong in the log,",
          "which is what makes this one costly.",
          "",
          "**The fix:** only the actual fill rectangle keeps the name `Image-Placeholder`.",
          "Rename its wrapper frame to `Image`.", ""]
    nested = 0
    for pname, root in full.items():
        for n in walk(root):
            if "placeholder" not in str(n.get("name", "")).lower():
                continue
            for c in n.get("children") or []:
                if "placeholder" in str(c.get("name", "")).lower():
                    nested += 1
                    L.append(f"- *{pname}*: `{n.get('name')}` contains `{c.get('name')}` "
                             f"— [{n['id']}]({link(n['id'])})")
    if not nested:
        L.append("_None found._")
    L.append("")

    # ---- 4. placeholder naming: NO ACTION NEEDED --------------------------
    # Kept as an explicit all-clear because it looks like a defect and is not.
    # The plugin's matcher (code.js:866) does
    #     (nm||"").toLowerCase().replace(/[_\s]+/g, "-")
    # so hyphen vs underscore vs case genuinely does not matter for photo slots.
    # Checked because 172 nodes use the underscore form; asking anyone to rename
    # those would have been a week of wasted work.
    L += ["---", "", "## 4. Photo slot naming: no action needed", "",
          "Most photo slots in the file use `Image_Placeholder` or `image_placeholder`",
          "rather than the documented `Image-Placeholder`. **This is fine and does not need",
          "fixing.** The plugin lowercases the name and treats underscores as hyphens before",
          "matching, so all three forms resolve to the same slot.", ""]
    variants = Counter()
    for pname, root in full.items():
        for n in walk(root):
            nm = str(n.get("name", ""))
            if n.get("type") == "TEXT":
                continue
            canon = nm.lower().replace("_", "-").replace(" ", "-")
            if canon in ("image-placeholder", "left-image-placeholder", "right-image-placeholder"):
                variants[nm] += 1
    for nm, count in variants.most_common():
        L.append(f"- `{nm}` on {count} node(s)")
    L.append("")
    odd = 0

    # ---- 5. more than one Rules card in a container ------------------------
    L += ["---", "", "## 5. Containers with more than one Rules card", "",
          "Whichever is read first wins. A stale card marked the whole ad type as blocked",
          "once. Delete the superseded one.", ""]
    multi = 0
    for pname, root in full.items():
        for cont in walk(root):
            nm = str(cont.get("name", ""))
            if not (nm.startswith("Adtype_") or nm.startswith("Reddit_Adtype_")):
                continue
            rules = [c for c in (cont.get("children") or []) if str(c.get("name")) == "Rules"]
            if len(rules) > 1:
                multi += 1
                L.append(f"- **{nm}** on *{pname}*: {len(rules)} Rules cards")
                for r in rules:
                    txt = next((t.get("characters", "") for t in walk(r)
                                if t.get("type") == "TEXT" and "Max" in str(t.get("characters", ""))), "")
                    L.append(f"    - [{r['id']}]({link(r['id'])}) — {box(r)[0]}x{box(r)[1]} "
                             f"{('reads: ' + ' '.join(txt.split())[:48]) if txt else ''}")
    if not multi:
        L.append("_None found._")
    L.append("")

    # ---- 6. pill labels on the off font ------------------------------------
    L += ["---", "", "## 6. Pill labels set in the wrong font", "",
          "Both pill labels in every board master use `Neue Montreal` while everything",
          "around them uses `PP Neue Montreal`. When that font is unavailable to whoever is",
          "running the plugin, those labels silently keep their placeholder text.",
          "",
          "The plugin now falls back automatically, so this is tidy-up rather than a",
          "blocker. Restyling them to PP Neue Montreal removes the dependency.", ""]
    offfont = Counter()
    examples = {}
    for pname, root in full.items():
        for n in walk(root):
            if n.get("type") != "TEXT":
                continue
            fam = ((n.get("style") or {}).get("fontFamily") or "")
            if fam and fam != "PP Neue Montreal":
                offfont[fam] += 1
                examples.setdefault(fam, (pname, n))
    for fam, count in offfont.most_common():
        pname, n = examples[fam]
        L.append(f"- `{fam}` on {count} text layer(s) — example on *{pname}*: "
                 f"`{n.get('name')}` [{n['id']}]({link(n['id'])})")
    L.append("")

    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  duplicate size frames : {dupes}")
    print(f"  nested photo slots    : {nested}")
    print(f"  off-standard slots    : {odd}  (naming variants are tolerated by design)")
    print(f"  multi Rules cards     : {multi}")


if __name__ == "__main__":
    main()
