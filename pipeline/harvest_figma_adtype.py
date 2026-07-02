#!/usr/bin/env python3
"""Harvest the 'Paid Acquisition 2026' Figma file into an ADAM-consumable registry.

Figma is the SOURCE OF TRUTH. This script derives, per visual style:
  - every size (1440x1440 / 1440x1800 / 1080x1920) and every variant
    (Dark/Light, Alt = No-CTA, Photo, carousel slide) — parsed from the
    template frame name `Template_{Style}_{Variant}_{WxH}` (also accepts the
    legacy `Adtype_` prefix so nothing is missed while Figma is standardized);
  - the canonical Figma node_id per (style, variant, size);
  - the exact text-layer names and their semantic ROLE (headline/subhead/cta/…);
  - the image-layer names and the image ROUTING (library photo / generate
    illustration / text-only);
  - the board master (`Meta - Static Grouped`) that the plugin clones per concept.

Output: configs/figma_adtype_registry.json  (read by the plugin + copy stage).
Re-run whenever Elise changes Figma:  python3 pipeline/harvest_figma_adtype.py
Requires FIGMA_ACCESS_TOKEN in the environment.
"""
import os, re, json, urllib.request
from pathlib import Path

FILE_ID = "DoDwumxELkuAuKKSP5p00e"
OUT = Path(__file__).parent.parent / "configs" / "figma_adtype_registry.json"

# ── size buckets (name-height may drift a few px; 1805/1880 → the 1800 slot) ──
CANON_SIZES = {"1440x1440", "1440x1800", "1080x1920"}
SIZES = [(1440, 1440, "1440x1440"), (1440, 1800, "1440x1800"), (1440, 1805, "1440x1800"),
         (1440, 1880, "1440x1800"), (1080, 1920, "1080x1920")]
def size_bucket(node):
    bb = node.get("absoluteBoundingBox") or {}
    w, h = bb.get("width"), bb.get("height")
    if not w or not h:
        return None
    for kw, kh, label in SIZES:
        if abs(w - kw) <= 16 and abs(h - kh) <= 16:
            return label            # always one of the 3 canonical sizes
    return None

# ── style-name normalization (align off-convention names to the standard) ──
STYLE_ALIASES = {
    "LifestylePhoto": "Lifestyle-Photo-Full-Bleed",
    "Adtype_Hybrid": "Hybrid",
    "Photo-With-Text": "Photo-with-Text",
    "Photo-With-Text-Alt": "Photo-with-Text",   # Alt folds into the style as a variant
    "Social-Profile": "Social-Media-Profile",
    "Adtype_Talent-Profile": "Talent-Profile",  # stray Adtype_ inside the frame name
}
# junk / WIP frame markers to ignore entirely
JUNK_RE = re.compile(r"(^|_)Copy(_|$)|^Lo$|Carousel", re.I)  # carousel handled separately

# ── text-layer role map (name → semantic field ADAM fills) ──
ROLE_RULES = [
    (re.compile(r"^Copy_Headline$|headline_text$|Headline_Text$", re.I), "headline"),
    (re.compile(r"^Copy_Subhead$|Subhead[_-]Text$|Subhead_Text$", re.I), "subhead"),
    (re.compile(r"^Copy_CTA$|^cta_text$|^Copy_Button$|^Button Label$", re.I), "cta"),
    (re.compile(r"^Copy_Body$|^Copy_Reminder$|Notification_Headline_Text$", re.I), "body"),
    (re.compile(r"^Copy_Bullet(\d)$", re.I), "bullet"),
    (re.compile(r"^Copy_(TopLeft|TopRight|BottomLeft|BottomRight)$", re.I), "quadrant"),
    (re.compile(r"^Copy_Title(\d)$", re.I), "title"),
    (re.compile(r"^Copy_(Left|Right)-Column$", re.I), "column"),
    (re.compile(r"^Copy_Name$", re.I), "profile_name"),
    (re.compile(r"^Copy_Title$", re.I), "profile_title"),
    (re.compile(r"^Copy_Author$", re.I), "author"),
    (re.compile(r"^Copy_Testimonial$", re.I), "testimonial"),
    (re.compile(r"^Copy_Chat-Bubble-(\d)$", re.I), "chat"),
    (re.compile(r"^Stat Block Text$", re.I), "stat"),
]
def role_of(name):
    for rx, role in ROLE_RULES:
        if rx.search(name or ""):
            return role
    return None

IMG_LIBRARY = re.compile(r"placeholder|texture|avatar|this-is-fine", re.I)
IMG_ILLUSTRATION = re.compile(r"illustration", re.I)

def figma(path):
    req = urllib.request.Request("https://api.figma.com/v1" + path,
                                 headers={"X-Figma-Token": os.environ["FIGMA_ACCESS_TOKEN"]})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)

def walk(n):
    yield n
    for c in n.get("children", []) or []:
        yield from walk(c)

def text_layers(fr):
    out = []
    for t in walk(fr):
        if t.get("type") == "TEXT":
            nm = t.get("name")
            out.append({"name": nm, "node_id": t.get("id"), "role": role_of(nm)})
    return out

def image_layers(fr):
    out = []
    for t in walk(fr):
        fills = t.get("fills") or []
        if isinstance(fills, list) and any(isinstance(f, dict) and f.get("type") == "IMAGE" for f in fills):
            nm = t.get("name") or ""
            if nm == "PrimaryGlimmer_Full":
                continue  # decorative gradient, not a content slot
            out.append({"name": nm, "node_id": t.get("id")})
    return out

NAME_RE = re.compile(r"^(?:Template|Adtype)_(.+)_(\d+x\d+)$")
def parse_name(nm):
    m = NAME_RE.match(nm)
    if not m:
        return None
    body, size = m.group(1), m.group(2)
    toks = body.split("_")
    variant = [t for t in toks if t.lower() in ("dark", "light", "alt", "photo")]
    style_toks = [t for t in toks if t not in variant]
    style = "_".join(style_toks).rstrip("-_")            # drop trailing _/- (e.g. 'Pie-Chart_')
    # 'Alt' can be baked into the style token (e.g. 'Photo-With-Text-Alt') — pull it out
    if re.search(r"-Alt$", style, re.I):
        style = re.sub(r"-Alt$", "", style, flags=re.I)
        variant.append("alt")
    style = STYLE_ALIASES.get(style, style)
    return style, "+".join(v.lower() for v in variant) if variant else "base", size

def routing_for(image_names):
    if any(IMG_ILLUSTRATION.search(n) for n in image_names):
        return "generate_illustration"
    if any(IMG_LIBRARY.search(n) for n in image_names):
        return "library_photo"
    return "text_only"

def main():
    print("fetching Figma file…")
    doc = figma(f"/files/{FILE_ID}")["document"]

    # collect canonical templates, dedup by (style, variant, size)
    styles = {}
    seen = set()
    for n in walk(doc):
        nm = n.get("name") or ""
        if not (nm.startswith("Template_") or nm.startswith("Adtype_")):
            continue
        if n.get("type") not in ("FRAME", "COMPONENT", "INSTANCE"):
            continue
        if JUNK_RE.search(nm) and "Carousel" not in nm:
            continue
        sb = size_bucket(n)
        if not sb:
            continue
        parsed = parse_name(nm)
        if not parsed:
            continue
        style, variant, size = parsed
        if size not in CANON_SIZES or style in ("Lo",) or len(style) < 3:
            continue                       # drop junk / WIP frames
        key = (style, variant, size)
        if key in seen:
            continue
        seen.add(key)
        imgs = image_layers(n)
        img_names = [i["name"] for i in imgs]
        styles.setdefault(style, {"variants": {}, "routing": None})
        styles[style]["variants"].setdefault(variant, {})[size] = {
            "node_id": n.get("id"),
            "frame_name": nm,
            "text_layers": text_layers(n),
            "image_layers": imgs,
        }
    # routing per style (union of its images)
    for style, data in styles.items():
        allimgs = [i["name"] for v in data["variants"].values()
                   for s in v.values() for i in s["image_layers"]]
        data["routing"] = routing_for(allimgs)

    # board master
    board = None
    for n in walk(doc):
        if n.get("name") == "Meta - Static Grouped" and n.get("children"):
            board = n
            break
    board_info = None
    if board:
        size_frames = {}
        for c in walk(board):
            sb = size_bucket(c)
            if sb and c.get("type") == "FRAME" and c.get("name", "").replace("x", "").isdigit() is False:
                # the three empty ad-slot frames live under 'Layout - Static Feed'
                pass
        # capture the 3 slot frames by their (mislabeled) names under Layout - Static Feed
        layout = next((c for c in walk(board) if c.get("name") == "Layout - Static Feed"), None)
        slots = {}
        if layout:
            for c in layout.get("children", []) or []:
                sb = size_bucket(c)
                if sb and c.get("type") == "FRAME":
                    slots[sb] = c.get("id")
        # left-panel copy value layers (positional: label text then value text)
        panel = next((c for c in walk(board) if c.get("name") == "Frame 15"), None)
        panel_texts = [{"name": t.get("name"), "node_id": t.get("id"),
                        "text": (t.get("characters") or "")[:40]}
                       for t in walk(panel) if t.get("type") == "TEXT"] if panel else []
        board_info = {
            "node_id": board.get("id"),
            "name": board.get("name"),
            "size_slots": slots,           # {size: frame node_id} to drop the assembled ad into
            "left_panel_texts": panel_texts,
        }

    out = {
        "source": "figma:" + FILE_ID,
        "convention": "Template_{Style}_{Variant}_{WxH}",
        "sizes": ["1440x1440", "1440x1800", "1080x1920"],
        "board_master": board_info,
        "styles": styles,
    }
    OUT.write_text(json.dumps(out, indent=2))
    # summary
    print(f"\nStyles: {len(styles)}   Board master: {'yes' if board_info else 'MISSING'}")
    for st in sorted(styles):
        d = styles[st]
        sizes = sorted({s for v in d["variants"].values() for s in v})
        print(f"  {st:28} routing={d['routing']:22} variants={list(d['variants'])} sizes={sizes}")
    print(f"\nwrote {OUT}")

if __name__ == "__main__":
    main()
