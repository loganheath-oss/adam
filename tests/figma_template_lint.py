#!/usr/bin/env python3
"""Figma template lint — detects the template/naming drift that silently breaks assembly.

Walks the "Paid Acquisition 2026" Figma file via the REST API and diffs reality against
what the assembly plugin expects. The expectations are EXTRACTED FROM plugin/code.js
(STYLE_TEMPLATE_PREFIXES + STYLE_ADTYPE_CONTAINERS) so this lint can never drift from
the plugin itself.

Catches the two 2026-07-27 assembly bugs class-wide:
  1. A style whose Adtype container/template names no longer match the plugin's map
     (Sticky Note: real container "Adtype_Sticky-Note" vs plugin's "Adtype: Sticky Note"
     -> silent fallback to the Testimonial placeholder).
  2. Nested duplicate image placeholders (Notification 4:5: FRAME named Image-Placeholder
     containing a RECT named Image-Placeholder -> photo filled UNDER the baked default).

Run:  railway run --service adam -- python3 tests/figma_template_lint.py
      (needs FIGMA_ACCESS_TOKEN in env; read-only, costs nothing)
Exit 0 = clean; 1 = findings.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Default = Paid Acquisition 2026 (configs/upwork_config.json). Assembly can also run
# in the KOTH file — pass its key as argv[1] to lint that one instead:
#   jmZfHnSCTbMYDb5WKNlAGf  (Paid Acquisition — King of The Hill 2026)
FILE_KEY = sys.argv[1] if len(sys.argv) > 1 else "DoDwumxELkuAuKKSP5p00e"
SIZES = ["1440x1440", "1440x1800", "1080x1920"]

TOK = os.environ.get("FIGMA_ACCESS_TOKEN", "")
if not TOK:
    print("FIGMA_ACCESS_TOKEN not in env — run via `railway run --service adam -- …`")
    sys.exit(1)


def api(path):
    req = urllib.request.Request(f"https://api.figma.com{path}", headers={"X-Figma-Token": TOK})
    return json.loads(urllib.request.urlopen(req, timeout=180).read())


def extract_js_map(src, var_name):
    """Pull a `var NAME = { "key": ["a","b"], … }` map out of plugin/code.js."""
    m = re.search(rf"var {var_name} = \{{(.*?)\n\}};", src, re.S)
    if not m:
        raise SystemExit(f"could not find {var_name} in plugin/code.js")
    body = m.group(1)
    out = {}
    for km in re.finditer(r'"([^"]+)":\s*\[([^\]]*)\]', body):
        out[km.group(1)] = re.findall(r'"([^"]+)"', km.group(2))
    return out


src = (REPO / "plugin" / "code.js").read_text()
PREFIXES = extract_js_map(src, "STYLE_TEMPLATE_PREFIXES")
CONTAINERS = extract_js_map(src, "STYLE_ADTYPE_CONTAINERS")

print(f"Figma template lint · file {FILE_KEY}")
print(f"  plugin expectations: {len(PREFIXES)} styles, {len(CONTAINERS)} container maps")

# One deep fetch of the whole document tree (name/type/children only via depth walk).
doc = api(f"/v1/files/{FILE_KEY}")["document"]

all_names = {}          # name -> count
frames_by_name = {}     # exact frame name -> node ids
nested_placeholder = []  # (ancestor name/id, descendant name/id)


def is_ph(nm):
    s = (nm or "").lower().replace("_", "-").replace(" ", "-")
    return s in ("image-placeholder", "left-image-placeholder", "right-image-placeholder")


def walk(n, ph_ancestor=None):
    nm = str(n.get("name", ""))
    all_names[nm] = all_names.get(nm, 0) + 1
    if n.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET", "SECTION", "GROUP"):
        frames_by_name.setdefault(nm, []).append(n.get("id"))
    here_ph = is_ph(nm)
    if here_ph and ph_ancestor is not None:
        nested_placeholder.append((ph_ancestor, f"{nm} ({n.get('id')})"))
    nxt = f"{nm} ({n.get('id')})" if here_ph else ph_ancestor
    for c in n.get("children", []):
        walk(c, nxt)


walk(doc)
findings = []

print("\n== per-style template resolution ==")
for style, prefixes in sorted(PREFIXES.items()):
    containers = CONTAINERS.get(style, [])
    container_hit = next((c for c in containers if c in all_names), None)
    # which template prefix actually resolves for at least one size?
    tpl_hits = []
    for p in prefixes:
        sizes_found = [s for s in SIZES if f"{p}_{s}" in all_names]
        if sizes_found:
            tpl_hits.append((p, sizes_found))
    primary = prefixes[0] if prefixes else ""
    primary_found = tpl_hits and tpl_hits[0][0] == primary
    status = "✅" if (container_hit and tpl_hits) else ("🟡" if tpl_hits else "❌")
    fallback_note = ""
    if tpl_hits and not primary_found:
        fallback_note = f" (PRIMARY '{primary}' missing — resolves via fallback '{tpl_hits[0][0]}')"
    missing_sizes = []
    if tpl_hits:
        missing_sizes = [s for s in SIZES if s not in tpl_hits[0][1]]
    print(f"  {status} {style:24} container={container_hit or 'NONE of ' + str(containers)}"
          f" tpl={tpl_hits[0][0] if tpl_hits else 'NONE of ' + str(prefixes)}"
          f"{' sizes-missing=' + str(missing_sizes) if missing_sizes else ''}{fallback_note}")
    if not container_hit:
        findings.append(f"{style}: no Adtype container matches {containers}")
    if not tpl_hits:
        findings.append(f"{style}: no template frames match any of {prefixes}")
    elif not primary_found:
        findings.append(f"{style}: primary template '{primary}' missing; using fallback '{tpl_hits[0][0]}'")
    if missing_sizes:
        findings.append(f"{style}: template '{tpl_hits[0][0]}' missing sizes {missing_sizes}")

print("\n== nested image-placeholders (photo fills land UNDER baked defaults) ==")
if nested_placeholder:
    seen = set()
    for anc, desc in nested_placeholder:
        k = (anc, desc)
        if k in seen:
            continue
        seen.add(k)
        print(f"  ❌ {anc}  contains  {desc}")
        findings.append(f"nested placeholder: {anc} contains {desc}")
else:
    print("  ✅ none")

print(f"\n{'CLEAN — plugin expectations match the file' if not findings else 'FINDINGS: ' + str(len(findings))}")
for f in findings:
    print("  ✗", f)
sys.exit(1 if findings else 0)
