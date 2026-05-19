"""
inspect_templates.py
====================
Dumps the layer structure of one or more Adtype containers in the Upwork Figma
file, so we can extend the assembly plugin (plugin/code.js) to handle new
styles without guessing layer names.

Output for each requested Adtype:
  - The Template_* descendants found inside it (these are what the plugin matches)
  - Each template's dimensions
  - For each template variant, every TEXT layer's name + current characters
  - For each template variant, every node with an image fill
  - All hidden tag-eligible nodes (rights expiration etc.)

Usage:
    export FIGMA_ACCESS_TOKEN='figd_...'
    python3 inspect_templates.py                          # all "Adtype:" containers
    python3 inspect_templates.py --adtype "Text with Button" "Notification"
    python3 inspect_templates.py --json out.json          # also dump raw JSON

Reads FIGMA_FILE_ID env var (defaults to the Upwork file).
"""

import json
import os
import ssl
import sys
import urllib.request
from typing import Any, Optional

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

FIGMA_API_BASE     = "https://api.figma.com/v1"
FIGMA_ACCESS_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FIGMA_FILE_ID      = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")


def figma_get(path: str, timeout: int = 30) -> dict:
    if not FIGMA_ACCESS_TOKEN:
        raise EnvironmentError(
            "FIGMA_ACCESS_TOKEN is not set. Export it:\n"
            "  export FIGMA_ACCESS_TOKEN='figd_...'"
        )
    req = urllib.request.Request(
        f"{FIGMA_API_BASE}{path}",
        headers={"X-Figma-Token": FIGMA_ACCESS_TOKEN},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Tree walking ─────────────────────────────────────────────────────────────

def find_nodes_where(root: dict, predicate) -> list[dict]:
    out: list[dict] = []
    def walk(n: dict) -> None:
        if not isinstance(n, dict):
            return
        if predicate(n):
            out.append(n)
        for c in n.get("children") or []:
            walk(c)
    walk(root)
    return out


def has_image_fill(node: dict) -> bool:
    fills = node.get("fills") or []
    if not isinstance(fills, list):
        return False
    return any(isinstance(f, dict) and f.get("type") == "IMAGE" for f in fills)


def node_size(node: dict) -> Optional[tuple[int, int]]:
    box = node.get("absoluteBoundingBox") or {}
    w = box.get("width")
    h = box.get("height")
    if w is None or h is None:
        return None
    return (round(w), round(h))


def short_type(node: dict) -> str:
    return node.get("type", "?")


# ── Structured dump per template ─────────────────────────────────────────────

def summarize_template(template: dict) -> dict:
    size = node_size(template)
    text_layers = []
    image_fill_layers = []
    hidden_tag_layers = []

    def walk(n: dict, depth: int = 0) -> None:
        if not isinstance(n, dict):
            return
        t = short_type(n)
        nm = n.get("name", "")
        if t == "TEXT":
            text_layers.append({
                "name": nm,
                "characters": (n.get("characters") or "")[:200],
                "size": node_size(n),
            })
        if has_image_fill(n):
            image_fill_layers.append({
                "name": nm,
                "type": t,
                "size": node_size(n),
            })
        if n.get("visible") is False and t in {"RECTANGLE", "FRAME", "INSTANCE", "COMPONENT", "ELLIPSE", "GROUP"}:
            hidden_tag_layers.append({
                "name": nm,
                "type": t,
            })
        for c in n.get("children") or []:
            walk(c, depth + 1)

    walk(template)

    # Tree outline (flat, indented) to reveal naming structure for plugin matching
    outline_lines: list[str] = []
    def outline(n: dict, depth: int) -> None:
        if not isinstance(n, dict):
            return
        prefix = "  " * depth
        size_str = ""
        sz = node_size(n)
        if sz:
            size_str = f" [{sz[0]}x{sz[1]}]"
        vis_str = ""
        if n.get("visible") is False:
            vis_str = " (hidden)"
        text_preview = ""
        if short_type(n) == "TEXT":
            chars = (n.get("characters") or "").replace("\n", " ")
            if len(chars) > 60:
                chars = chars[:57] + "..."
            text_preview = f' = "{chars}"'
        outline_lines.append(
            f"{prefix}{n.get('name','')} <{short_type(n)}>{size_str}{vis_str}{text_preview}"
        )
        for c in n.get("children") or []:
            outline(c, depth + 1)
    outline(template, 0)

    return {
        "name": template.get("name", ""),
        "type": short_type(template),
        "size": size,
        "text_layers": text_layers,
        "image_fill_layers": image_fill_layers,
        "hidden_tag_layers": hidden_tag_layers,
        "outline": outline_lines,
    }


def collect_templates(adtype_root: dict) -> list[dict]:
    """Find every Template_* descendant of an Adtype container.

    Includes children of COMPONENT_SETs (variants) so we see each variant.
    """
    out: list[dict] = []

    def walk(n: dict) -> None:
        if not isinstance(n, dict):
            return
        nm = n.get("name", "")
        t = short_type(n)
        if isinstance(nm, str) and nm.startswith("Template_"):
            if t == "COMPONENT_SET":
                # Variants are the actual templates the assembly plugin matches against
                for v in n.get("children") or []:
                    out.append({"variant_of": nm, "node": v})
                return  # don't recurse into variants twice
            else:
                out.append({"variant_of": None, "node": n})
                return
        for c in n.get("children") or []:
            walk(c)

    walk(adtype_root)
    return out


# ── Main ─────────────────────────────────────────────────────────────────────

def find_adtype_containers(document: dict, wanted: Optional[list[str]] = None) -> list[dict]:
    """Return Adtype: containers from the document.

    `wanted` is a list of style names without the "Adtype: " prefix (e.g.,
    ["Text with Button", "Notification"]). If None, returns every node whose
    name begins with "Adtype:".
    """
    def is_adtype(n: dict) -> bool:
        nm = n.get("name", "")
        if not isinstance(nm, str) or not nm.startswith("Adtype:"):
            return False
        if wanted is None:
            return True
        suffix = nm[len("Adtype:"):].strip()
        return any(suffix == w or w in suffix for w in wanted)

    return find_nodes_where(document, is_adtype)


def main(argv: list[str]) -> int:
    wanted: Optional[list[str]] = None
    json_out: Optional[str] = None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--adtype":
            wanted = []
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                wanted.append(argv[i])
                i += 1
            continue
        if a == "--json":
            i += 1
            json_out = argv[i] if i < len(argv) else None
            i += 1
            continue
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        i += 1

    print(f"→ Fetching file {FIGMA_FILE_ID} from Figma…")
    file_data = figma_get(f"/files/{FIGMA_FILE_ID}")
    document  = file_data.get("document") or {}

    adtypes = find_adtype_containers(document, wanted)
    if not adtypes:
        if wanted:
            print(f"  No Adtype containers matched: {wanted}")
        else:
            print("  No Adtype containers found in file.")
        return 1

    report: list[dict] = []

    for adtype in adtypes:
        print("\n" + "=" * 78)
        print(f"ADTYPE: {adtype.get('name','')}")
        print("=" * 78)

        templates = collect_templates(adtype)
        if not templates:
            print("  (no Template_* descendants found)")
            report.append({
                "adtype": adtype.get("name", ""),
                "templates": [],
            })
            continue

        adtype_entry = {
            "adtype": adtype.get("name", ""),
            "templates": [],
        }

        for entry in templates:
            tpl = entry["node"]
            variant_of = entry["variant_of"]
            summary = summarize_template(tpl)
            if variant_of:
                summary["variant_of"] = variant_of

            print("")
            label = f"{summary['name']} <{summary['type']}>"
            if summary.get("size"):
                label += f" [{summary['size'][0]}x{summary['size'][1]}]"
            if variant_of:
                label += f"  (variant of {variant_of})"
            print(f"--- {label} ---")

            print("  Text layers:")
            if summary["text_layers"]:
                for tl in summary["text_layers"]:
                    sz = f" [{tl['size'][0]}x{tl['size'][1]}]" if tl["size"] else ""
                    chars = (tl["characters"] or "").replace("\n", " ")
                    if len(chars) > 60:
                        chars = chars[:57] + "..."
                    print(f"    - {tl['name']}{sz}  =  \"{chars}\"")
            else:
                print("    (none)")

            print("  Image-fill layers:")
            if summary["image_fill_layers"]:
                for il in summary["image_fill_layers"]:
                    sz = f" [{il['size'][0]}x{il['size'][1]}]" if il["size"] else ""
                    print(f"    - {il['name']} <{il['type']}>{sz}")
            else:
                print("    (none)")

            if summary["hidden_tag_layers"]:
                print("  Hidden tag-eligible nodes:")
                for hl in summary["hidden_tag_layers"]:
                    print(f"    - {hl['name']} <{hl['type']}>")

            print("  Outline:")
            for line in summary["outline"]:
                print(f"    {line}")

            adtype_entry["templates"].append(summary)

        report.append(adtype_entry)

    if json_out:
        with open(json_out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n→ JSON written to {json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
