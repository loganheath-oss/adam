#!/usr/bin/env python3
"""Which Figma frame does the plugin pick for every style x size? Replayed live.

WHY THIS EXISTS
---------------
Elise, working session 2026-09-29, dropped the "template_style_name_" front
bumper: a template is now named for its size ("1440x1440", "Dark_1440x1800",
"Alt1_Light_1080x1920") and its container ("Meta_Adtype_Testimonial") says which
channel and style it is. She renamed the whole Meta page that night.

tests/figma_template_lint.py checks NAMES document-wide, so it reported that
rename as missing templates while old copies on the legacy "⚙️ Template Library"
page masked the rest. This replays what the plugin actually does instead:
templateSearchRoots order, findTemplateByConvention (name match, then the
container-and-size fallback), then the legacy prefix maps — and asserts every
style resolves on its OWN platform page, not the legacy library.

Ports from plugin/code.js (keep in step): _stripPlatformBumper, findAllByPrefix,
findTemplateByConvention, STYLE_ADTYPE_ALIAS, templateSearchRoots, and the
findStyledTemplate legacy fallback. It stops at the candidate list; variant
choice among candidates (selectVariant) is covered by tests/test_select_variant.js.

Run:  railway run --service adam -- python3 scripts/verify_template_resolution.py [meta|reddit|all]
      (read-only; the current page is assumed to be "Assembly", where Elise runs it)
Exit 0 = every style x size resolves on its platform page.
"""
import json
import os
import re
import sys
import urllib.request

FILE_KEY = "DoDwumxELkuAuKKSP5p00e"
TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
CODE = open(os.path.join(os.path.dirname(__file__), "..", "plugin", "code.js")).read()
CURRENT_PAGE = "Assembly"

PLATFORMS = {
    "meta": {
        "sizes": [(1440, 1440), (1440, 1800), (1080, 1920)],
        # Canonical Visual_Style values as they reach the manifest
        # (test_all_styles_manifest.csv), plus the two it lacks.
        "styles": ["Graphic with Text", "Split Screen", "Us vs Them", "Photo with Text",
                   "Lifestyle Photo", "Testimonial", "Social Media Profile", "Pie Chart", "Hybrid",
                   "Search Results", "Text Only", "Chat Bubble", "Reminder", "Device UI",
                   "Platform UI", "Meme", "Sticky Note", "Poll", "Tweet / Post Mockup",
                   "Text with Button", "Talent Profile", "Notification"],
    },
    "reddit": {
        "sizes": [(1080, 1350), (1440, 1080)],
        # REDDIT_STYLES in web/app/new/page.tsx.
        "styles": ["Graphic with Text", "Split Screen", "Us vs Them", "Person with Text",
                   "Person Only", "Testimonial", "Text Only", "Text with Icons", "Meme",
                   "Pie Chart", "Venn Diagram", "Notification", "App Notification", "Note",
                   "Button", "Search", "Search and Checkbox", "Icon", "Twitter", "Logo"],
    },
}

BUMPERS = {"meta", "reddit", "linkedin", "youtube", "google", "thirdparty"}


def api(path):
    req = urllib.request.Request("https://api.figma.com/v1/" + path,
                                 headers={"X-Figma-Token": TOKEN, "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def js_map(var):
    m = re.search(rf"var {var} = \{{(.*?)\n\}};", CODE, re.S)
    out = {}
    for km in re.finditer(r'"([^"]+)":\s*(\[[^\]]*\]|"[^"]*")', m.group(1)):
        v = km.group(2)
        out[km.group(1)] = re.findall(r'"([^"]+)"', v) if v.startswith("[") else v.strip('"')
    return out


ALIAS = js_map("STYLE_ADTYPE_ALIAS")
PREFIXES = js_map("STYLE_TEMPLATE_PREFIXES")
CONTAINERS = js_map("STYLE_ADTYPE_CONTAINERS")


def alnum(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"/+$", "", str(s or ""))).strip().lower()


def strip_bumper(name):
    s = str(name or "")
    m = re.match(r"^([A-Za-z0-9 &/]+?)\s*[_-]\s*(.+)$", s)
    if not m:
        return s
    t = re.sub(r"[^a-z0-9]", "", m.group(1).lower())
    if t in ("3rdpartyaffiliate", "thirdpartyaffiliate"):
        t = "thirdparty"
    if t.startswith("google"):
        t = "google"
    return m.group(2) if t in BUMPERS else s


def walk(n):
    yield n
    for c in n.get("children") or []:
        yield from walk(c)


def by_prefix(node, prefix):
    exact = [n for n in walk(node) if n.get("name") and
             (n["name"].startswith(prefix) or strip_bumper(n["name"]).startswith(prefix))]
    if exact:
        return exact
    w = norm(prefix)
    return [n for n in walk(node) if n.get("name") and
            (norm(n["name"]).startswith(w) or norm(strip_bumper(n["name"])).startswith(w))]


def box(n):
    b = n.get("absoluteBoundingBox") or {}
    return (round(b["width"]), round(b["height"])) if b else None


def size_of(n):
    m = re.search(r"(\d{3,5})\s*[x×]\s*(\d{3,5})", str(n.get("name")), re.I)
    return (int(m.group(1)), int(m.group(2))) if m else box(n)


def fits(n, w, h):
    s = size_of(n)
    return bool(s) and s[0] == w and abs(s[1] - h) <= 12


def by_convention(root, style, w, h):
    raw = alnum(style)
    an = ALIAS.get(raw, raw)
    # Templates are frames, never TEXT (plugin _templateFramesByPrefix).
    hits = [c for c in by_prefix(root, "Template") + by_prefix(root, "Adtype")
            if c.get("type") != "TEXT" and an in alnum(c["name"]) and fits(c, w, h)]
    if hits:
        return hits, "by name"
    wants = ["adtype" + raw, "adtype" + an] if raw != an else ["adtype" + an]
    sects = [s for s in by_prefix(root, "Adtype") + by_prefix(root, "Reddit_Adtype") if "children" in s]
    cont = (next((s for want in wants for s in sects if alnum(s["name"]).endswith(want)), None) or
            next((s for want in wants for s in sects if want in alnum(s["name"])), None))
    if not cont:
        return [], ""
    kids = by_prefix(cont, "Template") or [k for k in cont.get("children", [])
                                           if k["type"] in ("FRAME", "COMPONENT", "COMPONENT_SET")]
    return [k for k in kids if fits(k, w, h)], "in " + cont["name"]


def by_legacy(root, style, w, h):
    key = re.sub(r"\s+", " ", style.strip().lower())
    for p in PREFIXES.get(key, []):
        for c in by_prefix(root, p):
            if box(c) == (w, h):
                return [c]
    return []


def main():
    if not TOKEN and "--file" not in sys.argv:
        sys.exit("FIGMA_ACCESS_TOKEN not set (run via: railway run --service adam -- ...)")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    which = args[0] if args else "all"
    # --file PATH: check a saved (e.g. post-rename) copy instead of the live file.
    if "--file" in sys.argv:
        doc = json.load(open(sys.argv[sys.argv.index("--file") + 1]))["document"]
        which = next((a for a in args if a in ("meta", "reddit", "all")), "all")
    else:
        doc = api(f"files/{FILE_KEY}")["document"]
    pages = doc["children"]
    page_of = {n["id"]: p["name"].strip() for p in pages for n in walk(p)}

    problems = 0
    for plat in (["meta", "reddit"] if which == "all" else [which]):
        roots, seen = [], set()

        def push(n, why):
            if n and n["id"] not in seen:
                seen.add(n["id"])
                roots.append((n, why))

        push(next((p for p in pages if p["name"].strip() == CURRENT_PAGE), None), "current page")
        home = [p for p in pages if plat in alnum(p["name"]) and "template" in alnum(p["name"])]
        for p in home:
            push(p, "platform page")
        for p in pages:
            if re.search("template", p["name"], re.I):
                push(p, "template page")
        push(doc, "entire document")
        home_names = {p["name"].strip() for p in home}

        spec = PLATFORMS[plat]
        print(f"\n== {plat}: {len(spec['styles'])} styles x {len(spec['sizes'])} sizes "
              f"(platform page: {', '.join(sorted(home_names)) or 'NONE'}) ==")
        for style in spec["styles"]:
            for w, h in spec["sizes"]:
                found, how, where = [], "", ""
                for root, why in roots:
                    found, how = by_convention(root, style, w, h)
                    if not found:
                        found, how = by_legacy(root, style, w, h), "legacy prefix"
                    if found:
                        where = why
                        break
                if not found:
                    problems += 1
                    print(f"  ✗ {style:22} {w}x{h}  NOT FOUND")
                    continue
                page = page_of.get(found[0]["id"], "?")
                ok = page in home_names
                problems += 0 if ok else 1
                names = ", ".join(f["name"] for f in found[:5]) + (" …" if len(found) > 5 else "")
                print(f"  {'✓' if ok else '✗'} {style:22} {w}x{h}  {how}: {names}"
                      + ("" if ok else f"   <-- from '{page}' via {where}, not the {plat} page"))

    print(f"\n{'ALL RESOLVE on their platform page' if not problems else f'PROBLEMS: {problems}'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
