#!/usr/bin/env python3
"""Static proof for the Reddit assembly release, run BEFORE touching plugin/code.js.

Plugin code only runs in Figma desktop. This replays the CURRENT and PROPOSED
lookup logic against live ADAM 2026 JSON and asserts the proposed behaviour, so
a change can be justified without running it. Two "verified" claims have already
shipped false confidence on this surface (effdc1b's node-shape check, and a
structural check accidentally run against a superseded stub), which is why every
assertion below names the node id it ran against.

Run:  railway run python3 scripts/verify_plugin_changes.py
Exit code 0 = every assertion held.
"""
import json
import os
import re
import sys
import urllib.request

FILE_KEY = "DoDwumxELkuAuKKSP5p00e"
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
CODE = open(os.path.join(os.path.dirname(__file__), "..", "plugin", "code.js")).read()

REDDIT_MASTER = "7356:1259"   # Reddit - Static Grouped  (Elise's link, current)
REDDIT_STUB = "7023:1262"     # Reddit - Static Grouped/Reddit - Image Feed (superseded)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def api(path):
    req = urllib.request.Request(
        "https://api.figma.com/v1/" + path,
        headers={"X-Figma-Token": TOKEN, "User-Agent": "Mozilla/5.0"},
    )
    return json.load(urllib.request.urlopen(req, timeout=180))


# ── ports (see scripts/figma_board_master_audit.py for provenance) ───────────

def norm_alnum(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def norm_name(s):
    return re.sub(r"\s+", " ", re.sub(r"/+$", "", str(s or ""))).strip().lower()


def walk(n):
    yield n
    for c in n.get("children") or []:
        yield from walk(c)


def box(n):
    b = n.get("absoluteBoundingBox") or {}
    return (round(b.get("width", 0)), round(b.get("height", 0))) if b else (0, 0)


def find_all_by_prefix(node, prefix):
    exact = [n for n in walk(node) if str(n.get("name", "")).startswith(prefix)]
    if exact:
        return exact
    want = norm_name(prefix)
    return [n for n in walk(node) if norm_name(n.get("name")).startswith(want)]


# ── CURRENT behaviour ────────────────────────────────────────────────────────

def old_find_board_master(pages_in_order):
    """Literal exact-name walk, document order."""
    for p in pages_in_order:
        for n in walk(p):
            if n.get("name") == "Meta - Static Grouped" and n.get("type") == "FRAME":
                return n
    return None


def old_section_lookup(root, style, w, h):
    an = norm_alnum(style)
    want = "adtype" + an
    sects = find_all_by_prefix(root, "Adtype") + find_all_by_prefix(root, "Reddit_Adtype")
    container = next((s for s in sects if want in norm_alnum(s.get("name"))), None)
    return _match_in_container(container, w, h)


# ── PROPOSED behaviour ───────────────────────────────────────────────────────

def new_find_board_master(pages_in_order, token):
    """Exact literal for meta/empty (byte-for-byte today), else whole-name alnum."""
    want = (token or "") + "staticgrouped"
    for p in pages_in_order:
        for n in walk(p):
            if n.get("type") != "FRAME":
                continue
            if not token or token == "meta":
                if n.get("name") == "Meta - Static Grouped":
                    return n
            elif norm_alnum(n.get("name")) == want:
                return n
    return None


def new_section_lookup(root, style, w, h):
    """children-guard + exact-tail preference, then today's substring pass."""
    an = norm_alnum(style)
    want = "adtype" + an
    sects = [
        s
        for s in find_all_by_prefix(root, "Adtype") + find_all_by_prefix(root, "Reddit_Adtype")
        if "children" in s                                    # amendment B1
    ]
    container = next((s for s in sects if norm_alnum(s.get("name")).endswith(want)), None)
    if container is None:                                     # amendment B2 fallback
        container = next((s for s in sects if want in norm_alnum(s.get("name"))), None)
    return _match_in_container(container, w, h)


def _match_in_container(container, w, h):
    if container is None:
        return None, None
    kids = find_all_by_prefix(container, "Template")
    if not kids:
        kids = [
            c for c in (container.get("children") or [])
            if c.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET")
        ]
    for k in kids:
        m = re.search(r"(\d{3,5})\s*[x×]\s*(\d{3,5})", str(k.get("name")), re.I)
        kw, kh = (int(m.group(1)), int(m.group(2))) if m else box(k)
        if kw == w and abs(kh - h) <= 12:
            return container, k
    return container, None


def resolve_slot_target(frame):
    """Descend into a wrapper holding exactly one large, strictly-smaller FRAME."""
    inner, n = None, 0
    for c in frame.get("children") or []:
        if c.get("type") == "FRAME":
            w, h = box(c)
            if w >= 800 and h >= 800:
                inner, n = c, n + 1
    if n == 1:
        iw, ih = box(inner)
        fw, fh = box(frame)
        if iw < fw or ih < fh:
            return inner
    return frame


def collect_slots(master):
    lay = next((n for n in walk(master) if n.get("name") == "Layout - Static Feed"), None)
    if not lay:
        return []
    out = []
    for c in lay.get("children") or []:
        if c.get("type") == "FRAME":
            w, h = box(c)
            if w >= 800 and h >= 800:
                out.append(c)
    return out


def main():
    if not TOKEN:
        sys.exit("FIGMA_ACCESS_TOKEN not set (run via: railway run)")

    shallow = api(f"files/{FILE_KEY}?depth=1")
    page_ids = [(p["name"], p["id"]) for p in shallow["document"]["children"]]
    cache = {}

    def page(pid):
        if pid not in cache:
            cache[pid] = api(f"files/{FILE_KEY}/nodes?ids={pid}")["nodes"][pid]["document"]
        return cache[pid]

    pages = [page(pid) for _, pid in page_ids]
    node_by_id = {}
    for p in pages:
        for n in walk(p):
            node_by_id[n.get("id")] = n

    print(f"FILE {shallow.get('name')}  lastModified {shallow.get('lastModified')}")
    print()

    # ── A. board master ──────────────────────────────────────────────────────
    print("A. PLATFORM-AWARE BOARD MASTER")
    got = new_find_board_master(pages, "reddit")
    check("A1 reddit token resolves to Elise's master 7356:1259",
          got is not None and got.get("id") == REDDIT_MASTER,
          f"got {got and got.get('id')} {got and got.get('name')!r}")
    check("A1b the superseded stub is rejected",
          got is None or got.get("id") != REDDIT_STUB)
    all_sg = [n for p in pages for n in walk(p)
              if n.get("type") == "FRAME" and norm_alnum(n.get("name")).endswith("staticgrouped")]
    print(f"       whole-name '*staticgrouped' FRAMEs: {len(all_sg)}")
    for n in all_sg:
        print(f"         {norm_alnum(n.get('name')):40} {n.get('id')}  {n.get('name')!r}")
    # Meta deliberately has many identical masters (4 on Template Library, 4 on
    # Meta Templates) and has ALWAYS been first-match-wins among them. The
    # requirement there is "picks the same node as today", which A3 proves —
    # not uniqueness. Uniqueness is required only for the platforms the new
    # matcher newly reaches.
    meta_hits = [n for n in all_sg if norm_alnum(n.get("name")) == "metastaticgrouped"]
    check("A2 meta has >1 master and stays first-match-wins (uniqueness NOT required)",
          len(meta_hits) > 1, f"{len(meta_hits)} masters, pick verified by A3")
    for tok in ("reddit", "linkedin", "youtube", "google", "thirdparty"):
        hits = [n for n in all_sg if norm_alnum(n.get("name")) == tok + "staticgrouped"]
        check(f"A2 token '{tok}' matches exactly one master",
              len(hits) == 1, f"{len(hits)} hit(s): {[h.get('id') for h in hits]}")
    check("A2b bogus token matches nothing",
          new_find_board_master(pages, "tiktok") is None)
    old, new = old_find_board_master(pages), new_find_board_master(pages, "")
    check("A3 empty token picks the identical node the old walk picks",
          old is not None and new is not None and old.get("id") == new.get("id"),
          f"old={old and old.get('id')} new={new and new.get('id')}")
    print()

    # ── B. container shadowing ───────────────────────────────────────────────
    print("B. CONTAINER LOOKUP (spec-card TEXT labels shadow real containers)")
    rpid = next(pid for nm, pid in page_ids if "Reddit Templates" in nm)
    rroot = page(rpid)
    guide = json.load(open("configs/ad_type_style_guide.json"))["entries"]
    rstyles = [(k, v.get("name", k).split("—")[-1].strip())
               for k, v in guide.items() if k.startswith("reddit-")]
    old_hits = new_hits = 0
    bad = []
    for key, style in rstyles:
        for (w, h) in ((1080, 1350), (1440, 1080)):
            _, of = old_section_lookup(rroot, style, w, h)
            nc, nf = new_section_lookup(rroot, style, w, h)
            old_hits += bool(of)
            new_hits += bool(nf)
            if not nf:
                bad.append((style, w, h, nc and nc.get("name")))
    check("B4 all 20 Reddit styles x 2 sizes resolve after the fix",
          new_hits == 40, f"before={old_hits}/40  after={new_hits}/40")
    if bad:
        for s, w, h, c in bad[:8]:
            print(f"         MISS {s} @ {w}x{h} (container {c})")
    for style, expect in (("Search", "Reddit_Adtype_Search"),
                          ("Search and Checkbox", "Reddit_Adtype_Search-and-Checkbox")):
        c, _ = new_section_lookup(rroot, style, 1080, 1350)
        check(f"B4b '{style}' lands in {expect}",
              c is not None and c.get("name") == expect,
              f"got {c and c.get('name')!r}")
    # B5 Meta regression gate
    prefixes = re.search(r"var STYLE_TEMPLATE_PREFIXES\s*=\s*\{(.*?)\n\};", CODE, re.S)
    mstyles = re.findall(r'"([^"]+)"\s*:', prefixes.group(1)) if prefixes else []
    mpid = next(pid for nm, pid in page_ids if "Meta Templates" in nm)
    mroot = page(mpid)
    changed, converted = [], []
    for style in mstyles:
        for (w, h) in ((1440, 1440), (1440, 1800), (1080, 1920)):
            _, o = old_section_lookup(mroot, style, w, h)
            _, n = new_section_lookup(mroot, style, w, h)
            if o and n and o.get("id") != n.get("id"):
                changed.append((style, w, h, o.get("id"), n.get("id")))
            elif not o and n:
                converted.append((style, w, h, n.get("name")))
    check("B5 no Meta style changes its resolved node id",
          not changed, f"{len(changed)} changed")
    for s, w, h, oid, nid in changed[:6]:
        print(f"         CHANGED {s} @ {w}x{h}: {oid} -> {nid}")
    print(f"       MISS->HIT conversions on Meta (expected, a fix): {len(converted)}")
    for s, w, h, nm in converted[:8]:
        print(f"         {s} @ {w}x{h} -> {nm}")
    print()

    # ── C. slot descent ──────────────────────────────────────────────────────
    print("C. SLOT DESCENT")
    rm = node_by_id[REDDIT_MASTER]
    slots = collect_slots(rm)
    check("C7 Reddit master exposes exactly 2 outer slots", len(slots) == 2, f"{len(slots)}")
    inners = [resolve_slot_target(s) for s in slots]
    got_boxes = sorted(box(i) for i in inners)
    check("C7b descent yields exactly (1080,1350) and (1440,1080)",
          got_boxes == [(1080, 1350), (1440, 1080)], f"{got_boxes}")
    for s, i in zip(slots, inners):
        print(f"       wrapper {s.get('name')!r} {box(s)} layoutMode={s.get('layoutMode')!r}"
              f"  ->  inner {i.get('name')!r} {box(i)}")
    meta_masters = [n for n in all_sg if norm_alnum(n.get("name")) == "metastaticgrouped"]
    violations = []
    for mm in meta_masters:
        for s in collect_slots(mm):
            if resolve_slot_target(s).get("id") != s.get("id"):
                violations.append((mm.get("id"), s.get("name"), box(s)))
    check("C8 NO Meta slot descends (no-Meta-change proof)",
          not violations, f"{len(violations)} violation(s) across {len(meta_masters)} master(s)")
    for mid, nm, bx in violations[:6]:
        print(f"         master {mid} slot {nm!r} {bx}")
    labels_inside = all(
        any(t.get("type") == "TEXT" and re.search(r"\d{3,5}x\d{3,5}", str(t.get("characters") or ""))
            for t in walk(s))
        for s in slots
    )
    check("C9 Reddit size labels live INSIDE the wrapper (hiding outer hides label)",
          labels_inside)
    print()

    # ── D. copy panel + pills ────────────────────────────────────────────────
    print("D. COPY PANEL AND PILLS, ON 7356:1259 (not the stub)")
    names = {str(n.get("name")) for n in walk(rm)}
    check("D12a Reddit master has Frame 15", "Frame 15" in names)
    check("D12b Reddit master has NEITHER Frame 13 nor Frame 14",
          "Frame 13" not in names and "Frame 14" not in names)
    f15 = next((n for n in walk(rm) if n.get("name") == "Frame 15"), None)
    notes = next((c for c in (f15.get("children") or []) if c.get("name") == "Notes"), None) if f15 else None
    check("D11a 'Notes' is a DIRECT child of Frame 15", notes is not None)
    cf = next((c for c in (notes.get("children") or []) if c.get("name") == "Copy Frame"), None) if notes else None
    check("D11b 'Copy Frame' is a DIRECT child of Notes (fillCopyPanelByLabel requires this)",
          cf is not None)
    labels = []
    if cf:
        for g in cf.get("children") or []:
            if g.get("type") != "FRAME":
                continue
            ts = [t for t in (g.get("children") or []) if t.get("type") == "TEXT"]
            if len(ts) >= 2:
                labels.append((ts[0].get("characters") or "").strip())
    print(f"       copy rows: {labels}")
    low = " | ".join(labels).lower()
    check("D11c a headline row exists", "headline" in low)
    check("D11d a primary/body row exists", "primary" in low or "body" in low)
    if "cta" in low:
        print("       NOTE: a CTA row exists and fillCopyPanelByLabel HIDES it -> Elise note")
    content = next((n for n in walk(rm) if n.get("name") == "Content"), None)
    ad_info = next((c for c in (content.get("children") or []) if c.get("name") == "Ad Info"), None) if content else None
    check("D10a 'Ad Info' is a DIRECT child of 'Content' on the CURRENT master",
          ad_info is not None)
    if ad_info:
        for want in ("Ad Concept Number", "Ad Type"):
            pill = next((c for c in ad_info.get("children") or [] if c.get("name") == want), None)
            bl = next((t for t in walk(pill) if t.get("type") == "TEXT" and t.get("name") == "Button Label"), None) if pill else None
            font = ((bl or {}).get("style") or {}).get("fontPostScriptName")
            check(f"D10b pill '{want}' has a Button Label", bl is not None, f"font={font}")
        has_t = any(c.get("name") == "Targeting" for c in ad_info.get("children") or [])
        print(f"       Targeting pill present: {has_t}")
    for mm in meta_masters:
        mn = {str(n.get("name")) for n in walk(mm)}
        if not ("Frame 13" in mn and "Frame 14" in mn):
            check(f"D12c Meta master {mm.get('id')} has Frame 13 AND 14", False)
            break
    else:
        check("D12c every Meta master has Frame 13 AND Frame 14 (f15 branch can't fire on Meta)", True)
    print()

    # ── 13. end-to-end chain ─────────────────────────────────────────────────
    print("13. END-TO-END STATIC DRY RUN (Reddit)")
    master = new_find_board_master(pages, "reddit")
    ok = master is not None
    rows = 0
    for key, style in rstyles:
        for s in collect_slots(master) if master else []:
            tgt = resolve_slot_target(s)
            w, h = box(tgt)
            _, frame = new_section_lookup(rroot, style, w, h)
            rows += 1
            if not frame:
                ok = False
                print(f"       BREAK {style} @ {w}x{h}")
    check(f"13 every Reddit style reaches a template through the full chain ({rows} lookups)", ok)

    print()
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED: " + "; ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
