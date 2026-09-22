#!/usr/bin/env python3
"""Render a preview thumbnail for every Reddit ad type, straight from Figma.

Why this exists
---------------
The order form's style picker showed a preview for each Meta ad type and an
empty grey box for most Reddit ones — 13 of Reddit's 20 had no image at all,
and the 7 that did were showing the META artwork for a similarly-named style,
which is worse than blank because it is confidently wrong. A requester picking
"Split Screen" for Reddit was looking at Meta's Split Screen. (Adrie, live
testing, 2026-09-21.)

The Meta previews were pasted into the codebase as base64 from an old HTML
form, so there was no way to regenerate them and no way to add to them. This
script replaces that with something reproducible: it asks Figma to render the
real Reddit template frames and writes them out as ordinary public assets.

Rerun it whenever Elise changes a Reddit template.

    railway run --service adam python3 scripts/harvest_reddit_thumbs.py

Writes:
    web/public/style-previews/reddit/<slug>.jpg
    web/lib/reddit-style-thumbs.ts   (generated — do not hand-edit)
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FILE_KEY = json.loads((BASE_DIR / "configs" / "upwork_config.json").read_text())["figma"]["file_id"]

OUT_DIR = BASE_DIR / "web" / "public" / "style-previews" / "reddit"
OUT_TS = BASE_DIR / "web" / "lib" / "reddit-style-thumbs.ts"

# The order form's Reddit list, which is what the picker actually renders. Kept
# here explicitly rather than parsed out of the TSX so a rename on either side
# shows up as a missing thumbnail instead of silently drifting.
REDDIT_STYLES = [
    "Graphic with Text", "Split Screen", "Us vs Them", "Person with Text",
    "Person Only", "Testimonial", "Text Only", "Text with Icons", "Meme",
    "Pie Chart", "Venn Diagram", "Notification", "App Notification", "Note",
    "Button", "Search", "Search and Checkbox", "Icon", "Twitter", "Logo",
]


def norm(s):
    """Match the plugin's comparison: alphanumerics only, lowercased.

    plugin/code.js normalizes the same way, so "Us vs Them", "Us-Vs-Them" and
    "UsVsThem" are one name. Matching loosely here is deliberate: the Figma
    frames are named by hand and the form's labels are written for humans.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def api(path):
    # The User-Agent is load-bearing: Figma's edge answers 403 to urllib's
    # default agent, which reads as an auth failure and sends you looking at
    # the token. The other Figma scripts in here set it for the same reason.
    req = urllib.request.Request(
        f"https://api.figma.com{path}",
        headers={"X-Figma-Token": TOKEN, "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def walk(node, depth=0, parent=None):
    yield node, depth, parent
    for kid in node.get("children", []) or []:
        yield from walk(kid, depth + 1, node)


def pick_frame(container):
    """Choose the frame that best represents an ad type.

    A Reddit ad-type container holds one frame per size, and sometimes Light
    and Dark variants. Prefer a portrait 1080x1350 (Reddit's primary feed size,
    so it is what the requester will actually see) and prefer Light, because
    the picker sits on a white card. Fall back to the largest frame rather than
    the first, since the first child is often a spec card or a label.
    """
    frames = [
        n for n, _, _ in walk(container)
        if n.get("type") in ("FRAME", "COMPONENT", "INSTANCE")
        and n.get("absoluteBoundingBox")
        and n is not container
    ]
    if not frames:
        return None

    def score(n):
        box = n["absoluteBoundingBox"]
        w, h = round(box.get("width", 0)), round(box.get("height", 0))
        nm = norm(n.get("name", ""))
        s = 0
        if (w, h) == (1080, 1350):
            s += 100
        elif h > w:
            s += 40
        if "dark" in nm:
            s -= 30
        if "light" in nm:
            s += 10
        if "spec" in nm or "label" in nm or "cover" in nm:
            s -= 200
        s += min(w * h, 4_000_000) / 1_000_000
        return s

    return max(frames, key=score)


def main():
    if not TOKEN:
        sys.exit("FIGMA_ACCESS_TOKEN not set (run via: railway run --service adam ...)")

    # Page by page, never the whole file: a full /v1/files fetch on ADAM 2026
    # comes back 403 because the document is too large to serialize. Shallow
    # first for the page list, then one request per page.
    print(f"Reading Figma file {FILE_KEY} …")
    pages = api(f"/v1/files/{FILE_KEY}?depth=1")["document"]["children"]
    print(f"  {len(pages)} pages")

    nodes = []
    for p in pages:
        if "reddit" not in norm(p.get("name", "")):
            continue
        print(f"  reading page {p.get('name')!r} …")
        got = api(f"/v1/files/{FILE_KEY}/nodes?ids={p['id']}")["nodes"]
        nodes.append(got[p["id"]]["document"])

    if not nodes:
        # No page names itself Reddit, so fall back to reading every page and
        # letting the name match below decide. Slower, but correct.
        print("  no page named Reddit — reading all pages")
        for p in pages:
            got = api(f"/v1/files/{FILE_KEY}/nodes?ids={p['id']}")["nodes"]
            nodes.append(got[p["id"]]["document"])

    # Find each Reddit ad-type container. The live convention is
    # Reddit_Adtype_<Style>; older frames predate the prefix, so also accept a
    # bare Adtype_<Style> that lives under a page whose name mentions Reddit.
    containers = {}
    for node, _, _ in (x for root in nodes for x in walk(root)):
        name = node.get("name", "")
        n = norm(name)
        if not n.startswith("redditadtype") and not n.startswith("adtype"):
            continue
        if "children" not in node:
            continue
        key = n.replace("redditadtype", "", 1) if n.startswith("redditadtype") else None
        if key is None:
            continue
        containers.setdefault(key, node)

    print(f"  found {len(containers)} Reddit ad-type containers")

    # Map each form label to a container.
    wanted, missing = {}, []
    for label in REDDIT_STYLES:
        key = norm(label)
        node = containers.get(key)
        if node is None:
            # Tolerate small naming differences, e.g. the frame called
            # "App-Notification" vs the label "App Notification".
            hits = [v for k, v in containers.items() if k == key or k.endswith(key) or key.endswith(k)]
            node = hits[0] if len(hits) == 1 else None
        if node is None:
            missing.append(label)
            continue
        frame = pick_frame(node)
        if frame is None:
            missing.append(f"{label} (container has no frame)")
            continue
        wanted[label] = frame

    if missing:
        print("\n  NOT MATCHED — these keep an empty preview:")
        for m in missing:
            print(f"    · {m}")

    if not wanted:
        sys.exit("\nNothing to render. Check the ad-type naming in Figma.")

    # Ask Figma to render them. Batched, because the images endpoint renders
    # synchronously and a 20-node request can take a while.
    ids = [f["id"] for f in wanted.values()]
    urls = {}
    for i in range(0, len(ids), 8):
        chunk = ids[i:i + 8]
        print(f"  rendering {i + 1}-{i + len(chunk)} of {len(ids)} …")
        for attempt in range(3):
            try:
                res = api(f"/v1/images/{FILE_KEY}?ids={','.join(chunk)}&format=jpg&scale=1")
                urls.update({k: v for k, v in (res.get("images") or {}).items() if v})
                break
            except urllib.error.HTTPError as e:
                if attempt == 2:
                    raise
                print(f"    retry after {e.code}")
                time.sleep(3)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = {}
    for label, frame in wanted.items():
        url = urls.get(frame["id"])
        if not url:
            print(f"  ✗ {label}: Figma returned no image")
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        dest = OUT_DIR / f"{slug}.jpg"
        with urllib.request.urlopen(url, timeout=120) as r:
            dest.write_bytes(r.read())
        written[label] = f"/style-previews/reddit/{slug}.jpg"
        print(f"  ✓ {label:22s} → {dest.name} ({dest.stat().st_size // 1024} KB, from {frame['name']})")

    body = ",\n".join(f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in sorted(written.items()))
    OUT_TS.write_text(
        "// GENERATED by scripts/harvest_reddit_thumbs.py — do not hand-edit.\n"
        "// Rendered from the real Reddit templates in the ADAM 2026 Figma file, so\n"
        "// the picker shows Reddit artwork for Reddit ad types. Rerun the script\n"
        "// after a template change.\n"
        "export const REDDIT_STYLE_THUMBS: Record<string, string> = {\n"
        f"{body},\n"
        "};\n"
    )
    print(f"\nWrote {len(written)} previews and {OUT_TS.relative_to(BASE_DIR)}")
    if missing:
        print(f"{len(missing)} style(s) still have no preview — see the list above.")


if __name__ == "__main__":
    main()
