#!/usr/bin/env python3
"""Static audit of the Figma board masters + Reddit template resolvability.

WHY THIS EXISTS
---------------
Figma plugin code only runs in Figma desktop, so a plugin change cannot be
tested by whoever wrote it. This harness replays the plugin's own lookup logic
in Python against the LIVE file JSON from the REST API, so a change can be
verified statically before anyone runs it for real.

Ported faithfully from plugin/code.js (do not "improve" these ports; they are
meant to reproduce the plugin's behaviour, bugs included):
  - normAlnum()                  code.js  ~1430
  - _normName()                  code.js  ~274
  - findAllByPrefix()            code.js  ~330  (exact-then-normalized)
  - findTemplateByConvention()   code.js  ~1440-1520 (section fallback)
  - platform token derivation    code.js  ~582-589 (templateSearchRoots)

Run:  railway run python3 scripts/figma_board_master_audit.py
"""
import json
import os
import re
import sys
import urllib.request
from collections import Counter

FILE_KEY = "DoDwumxELkuAuKKSP5p00e"  # ADAM 2026
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")


def api(path):
    req = urllib.request.Request(
        "https://api.figma.com/v1/" + path,
        headers={"X-Figma-Token": TOKEN, "User-Agent": "Mozilla/5.0"},
    )
    return json.load(urllib.request.urlopen(req, timeout=120))


# ── ports of the plugin's helpers ────────────────────────────────────────────

def norm_alnum(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def norm_name(s):
    # code.js: strip trailing slashes, collapse whitespace, trim, lowercase.
    # NOTE: only TRAILING slashes. An interior "/" (as in
    # "Reddit - Static Grouped/Reddit - Image Feed") survives.
    return re.sub(r"\s+", " ", re.sub(r"/+$", "", str(s or ""))).strip().lower()


def walk(node):
    yield node
    for c in node.get("children") or []:
        yield from walk(c)


def find_all_by_prefix(node, prefix):
    exact = [n for n in walk(node) if str(n.get("name", "")).startswith(prefix)]
    if exact:
        return exact
    want = norm_name(prefix)
    return [n for n in walk(node) if norm_name(n.get("name")).startswith(want)]


def wh(n):
    bb = n.get("absoluteBoundingBox") or {}
    if not bb:
        return None
    return round(bb.get("width", 0)), round(bb.get("height", 0))


def platform_token(platform):
    t = re.sub(r"[^a-z0-9]", "", norm_name(platform))
    if t == "3rdpartyaffiliate":
        t = "thirdparty"
    if t.startswith("google"):
        t = "google"
    return t


# ── the section-fallback half of findTemplateByConvention ────────────────────

def resolve_via_section(search_root, visual_style, w, h):
    """Returns (container_name, matched_frame_name) or (None, None)."""
    an = norm_alnum(visual_style)
    want_sect = "adtype" + an
    sects = find_all_by_prefix(search_root, "Adtype") + find_all_by_prefix(
        search_root, "Reddit_Adtype"
    )
    container = None
    for s in sects:
        if want_sect in norm_alnum(s.get("name")):
            container = s
            break
    if not container:
        return None, None
    kids = find_all_by_prefix(container, "Template")
    if not kids:
        kids = [
            c
            for c in (container.get("children") or [])
            if c.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET")
        ]
    for k in kids:
        m = re.search(r"(\d{3,5})\s*[x×]\s*(\d{3,5})", str(k.get("name")), re.I)
        if m:
            kw, kh = int(m.group(1)), int(m.group(2))
        else:
            got = wh(k)
            if not got:
                continue
            kw, kh = got
        if kw == w and abs(kh - h) <= 12:
            return container.get("name"), k.get("name")
    return container.get("name"), None


# ── the audit ────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        sys.exit("FIGMA_ACCESS_TOKEN not set (run via: railway run)")

    shallow = api(f"files/{FILE_KEY}?depth=1")
    pages = {p["name"]: p["id"] for p in shallow["document"]["children"]}
    print(f"FILE: {shallow.get('name')}   lastModified: {shallow.get('lastModified')}")
    print()

    full_pages = {}

    def page(name):
        if name not in full_pages:
            pid = pages[name]
            full_pages[name] = api(f"files/{FILE_KEY}/nodes?ids={pid}")["nodes"][pid][
                "document"
            ]
        return full_pages[name]

    # ── 1. uniqueness of board masters ───────────────────────────────────────
    print("=" * 72)
    print("1. BOARD MASTER UNIQUENESS  (FRAMEs whose normalized name contains")
    print("   'static grouped'; the plugin takes the FIRST match)")
    print("=" * 72)
    masters = []
    for pname in pages:
        for n in walk(page(pname)):
            if n.get("type") != "FRAME":
                continue
            nn = norm_name(n.get("name"))
            if "static grouped" in nn:
                masters.append((pname, n.get("name"), n.get("id"), nn))
    by_platform = Counter()
    for pname, nm, nid, nn in masters:
        tok = "reddit" if "reddit" in nn else ("meta" if "meta" in nn else "other")
        by_platform[tok] += 1
        print(f"   [{tok:6}] {nm[:46]:48} page={pname.strip()[:26]:28} id={nid}")
    print(f"\n   counts: {dict(by_platform)}")
    if by_platform.get("reddit", 0) > 1:
        print("   *** AMBIGUOUS: more than one Reddit master, first-match-wins is unsafe")
    print()

    # ── 2 & 3. pill fonts + house font ───────────────────────────────────────
    print("=" * 72)
    print("2/3. PILL FONTS IN EACH MASTER, AND THE HOUSE FONT")
    print("=" * 72)
    fonts_seen = Counter()
    for pname, nm, nid, nn in masters:
        node = None
        for n in walk(page(pname)):
            if n.get("id") == nid:
                node = n
                break
        if node is None:
            continue
        ad_info = [n for n in walk(node) if n.get("name") == "Ad Info"]
        print(f"   MASTER {nm[:50]}")
        if not ad_info:
            print("      (no 'Ad Info' — pills will silently no-op here)")
        for ai in ad_info[:1]:
            for pill in ai.get("children") or []:
                for t in walk(pill):
                    if t.get("type") != "TEXT":
                        continue
                    st = t.get("style") or {}
                    cso = [x for x in (t.get("characterStyleOverrides") or []) if x]
                    print(
                        f"      {str(pill.get('name'))[:22]:24} "
                        f"{str(t.get('name'))[:14]:16} "
                        f"font={st.get('fontPostScriptName')} "
                        f"family={st.get('fontFamily')!r} "
                        f"mixed={bool(cso) or bool(t.get('styleOverrideTable'))}"
                    )
        for t in walk(node):
            if t.get("type") == "TEXT":
                st = t.get("style") or {}
                fonts_seen[(st.get("fontFamily"), st.get("fontPostScriptName"))] += 1
        print()
    print("   fonts across all masters (family, postscript) -> count:")
    for k, v in fonts_seen.most_common():
        print(f"      {str(k):58} {v}")
    print()

    # ── 4 & 5. reddit master internals ───────────────────────────────────────
    print("=" * 72)
    print("4/5. REDDIT MASTER: COPY PANELS + SLOT INVENTORY")
    print("=" * 72)
    reddit = [m for m in masters if "reddit" in m[3]]
    if not reddit:
        print("   NO REDDIT MASTER FOUND")
    for pname, nm, nid, nn in reddit:
        node = next(n for n in walk(page(pname)) if n.get("id") == nid)
        names = {str(n.get("name")) for n in walk(node)}
        print(f"   MASTER {nm}")
        print("   copy-panel layer names fillConceptBoard looks for:")
        for want in ("Frame 13", "Frame 14", "Notes", "Copy Frame"):
            print(f"      {want:12} present={want in names}")
        print("   FRAME children of 'Layout - Static Feed' (slots are w,h >= 800):")
        for lay in [n for n in walk(node) if n.get("name") == "Layout - Static Feed"]:
            for c in lay.get("children") or []:
                got = wh(c)
                if not got:
                    continue
                w, h = got
                is_slot = c.get("type") == "FRAME" and w >= 800 and h >= 800
                flag = "SLOT" if is_slot else "    "
                print(f"      {flag} {c.get('type'):10} {str(c.get('name'))[:30]:32} {w}x{h}")
        print("   size-label TEXT nodes (hide-unfilled logic matches these substrings):")
        for t in walk(node):
            if t.get("type") == "TEXT" and re.search(r"\d{3,5}x\d{3,5}", str(t.get("characters") or "")):
                print(f"      {t.get('characters')!r}")
        print()

    # ── 6. template resolvability for every Reddit style ─────────────────────
    print("=" * 72)
    print("6. TEMPLATE RESOLVABILITY (replay of findTemplateByConvention's")
    print("   section fallback) for all 20 Reddit styles at both sizes")
    print("=" * 72)
    guide = json.load(open("configs/ad_type_style_guide.json"))["entries"]
    reddit_styles = [
        v.get("name", k).split("—")[-1].strip()
        for k, v in guide.items()
        if k.startswith("reddit-")
    ]
    rpage = next(p for p in pages if "Reddit Templates" in p)
    root = page(rpage)
    bad = []
    for style in reddit_styles:
        line = f"   {style[:24]:26}"
        for (w, h) in ((1080, 1350), (1440, 1080)):
            cont, frame = resolve_via_section(root, style, w, h)
            if frame:
                line += f"  {w}x{h}=OK"
            else:
                line += f"  {w}x{h}=MISS"
                bad.append((style, w, h, cont))
        cont, _ = resolve_via_section(root, style, 1080, 1350)
        line += f"   container={str(cont)[:34]}"
        print(line)
    print()
    if bad:
        print("   MISSES:")
        for style, w, h, cont in bad:
            print(f"      {style} @ {w}x{h}  (container matched: {cont})")
    else:
        print("   all styles resolve at both sizes")

    # the Search / Search-and-Checkbox substring collision
    print()
    print("   substring-collision check, 'Search':")
    an = "adtype" + norm_alnum("Search")
    sects = find_all_by_prefix(root, "Adtype") + find_all_by_prefix(root, "Reddit_Adtype")
    hits = [s.get("name") for s in sects if an in norm_alnum(s.get("name"))]
    print(f"      containers matching '{an}' in page order: {hits}")
    if len(hits) > 1:
        print(f"      *** first-match-wins picks: {hits[0]}")


if __name__ == "__main__":
    main()
