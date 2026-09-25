#!/usr/bin/env python3
"""ADAM copy-engine regression suite.

Consolidates the ad-hoc verification harnesses from the 2026-07 quality work into a
committed, repeatable gate. Run BEFORE deploying pipeline/prompt/model changes.

Modes:
  python3 tests/copy_regression.py                 # offline: deterministic checks, free, no API
  python3 tests/copy_regression.py --live          # + real copy run, 6 styles (~$0.5)
  python3 tests/copy_regression.py --live --all    # + real copy run, all 24 styles (~$2-3)

Live mode needs ANTHROPIC_API_KEY in the env (run via `railway run --service adam -- …`
so the service key is injected without ever being printed). RUNS_DIR is always pointed
at a scratch dir — live tests NEVER touch real sprint data.

Exit code 0 = all checks pass; 1 = failures (printed).
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRATCH = Path(tempfile.mkdtemp(prefix="adam_regression_"))
# FORCE the scratch dir (never setdefault): `railway run` injects the service's
# RUNS_DIR=/data/runs, which is unreachable locally — and regression runs must
# never touch real sprint data regardless.
os.environ["RUNS_DIR"] = str(SCRATCH)
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import run_pipeline as rp  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


# All 24 order-form styles (must stay in sync with the /new form).
STYLES_24 = ["Graphic with Text", "Split Screen", "Us vs Them", "Photo with Text",
             "Lifestyle Photo", "Testimonial", "Social Media Profile", "Pie Chart",
             "Hybrid", "Search Results", "Search Bar with Talent Badge", "Text Only",
             "Chat Bubble", "Notification", "Reminder", "Device UI", "Platform UI",
             "Meme", "Sticky Note", "Poll", "Tweet / Post Mockup", "Text with Button",
             "Talent Profile", "Bespoke"]
# Styles allowed to have no style-guide entry (generic rules apply).
NO_GUIDE_OK = {"Search Bar with Talent Badge"}

# Prompted style-extra fields per normalized style (_sl) — mirrors the
# multi_field branches in _generate_copy_for_style. Used by BOTH the offline
# schema-coverage check and the live extras-presence check (2026-07-30: the
# live spec only verified creative_headline, so a run shipping Sticky concepts
# with NO sticky fields passed every check).
EXTRAS_BY_SL = {
    "usvsthem": ["us_headline", "them_headline", "us_bullets", "them_bullets"],
    "stickynote": ["left_headline", "right_headline", "left_bullets", "right_bullets"],
    "poll": ["poll_question", "poll_option_a", "poll_pct_a", "poll_option_b", "poll_pct_b"],
    "testimonial": ["testimonial_quote", "testimonial_author"],
    "searchresults": ["search_results"],
    "socialmediaprofile": ["profile_name", "profile_title", "profile_left", "profile_right"],
    "chatbubble": ["chat_label", "chat_message"],
    "textwithbutton": ["button_text"],
    "piechart": ["pie_labels", "pie_center"],
}


def _audience_photo_checks():
    """Prospecting and Retargeting must not share a photo inside one run.

    Adrie, 2026-09-10. Two versions of the SAME audience may share, because only
    one of them ships; the two audiences of one concept may not. The exclusion
    tiering in _pick_retargeting_photo is where that rule actually lives, so it
    is what gets tested here: the relaxed retry for a thin pool is allowed to
    drop the sprint-wide exclusions but never the sibling.
    """
    import sys as _sys
    import types as _types

    calls = []

    def _fake_module(pool):
        """Stand-in library: returns the first pool photo not excluded."""
        def pick_photo_for_asset(visual_style=None, order=None, sprint_id=None,
                                 components=None, exclude_ids=None, concept=None,
                                 temperature=None):
            ex = set(exclude_ids or [])
            calls.append(sorted(ex))
            for pid, name in pool:
                if pid not in ex:
                    return {"is_photo_based": True, "needs_human_selection": False,
                            "figma_asset_id": pid, "figma_asset_name": name}
            return {"is_photo_based": False, "needs_human_selection": True}
        m = _types.ModuleType("figma_library")
        m.pick_photo_for_asset = pick_photo_for_asset
        return m

    def _run(pool, used, sibling):
        calls.clear()
        saved = _sys.modules.get("figma_library")
        _sys.modules["figma_library"] = _fake_module(pool)
        try:
            return rp._pick_retargeting_photo(
                "Testimonial", {}, "sprint_x", [{"id": "c"}], {}, 1.0, used, sibling)
        finally:
            if saved is not None:
                _sys.modules["figma_library"] = saved
            else:
                del _sys.modules["figma_library"]

    POOL = [("p1", "one"), ("p2", "two"), ("p3", "three")]

    # Healthy pool: a distinct photo, and never the sibling.
    nid, _ = _run(POOL, used=["p1"], sibling=["p1"])
    check("audience photos: healthy pool returns a distinct photo", nid == "p2", f"got {nid!r}")

    # Thin pool: everything is used, so the retry must relax the sprint-wide
    # exclusions. It may repeat another concept's photo; it may NOT return p1.
    nid, _ = _run(POOL, used=["p1", "p2", "p3"], sibling=["p1"])
    check("audience photos: exhausted pool relaxes but still excludes the sibling",
          nid == "p2", f"got {nid!r}")
    check("audience photos: relaxed retry actually dropped the used-list",
          len(calls) == 2 and calls[1] == ["p1"], f"exclusion calls {calls}")

    # Only the sibling exists: refuse rather than duplicate across audiences.
    nid, name = _run([("p1", "one")], used=[], sibling=["p1"])
    check("audience photos: refuses to reuse the prospecting photo",
          (nid, name) == ("", ""), f"got {(nid, name)!r}")

    # Dual-photo styles chain the exclusion across all four picks.
    nid, _ = _run(POOL, used=[], sibling=["p1", "p2"])
    check("audience photos: dual-style chaining skips both siblings",
          nid == "p3", f"got {nid!r}")

    # The Both test the photo stage and the manifest writer share.
    check("audience photos: Both concept detected",
          rp._is_both_audience({"targeting_copy": {"Prospecting": {}}}) is True)
    for neg in ({}, {"targeting_copy": None}, {"targeting_copy": {}}, {"targeting_copy": "x"}):
        if rp._is_both_audience(neg):
            check("audience photos: single-audience concepts are NOT Both", False, repr(neg))
            break
    else:
        check("audience photos: single-audience concepts are NOT Both", True)


def _reddit_copy_shape_checks():
    """Reddit is ONE copy version; Meta is a long/short pair.

    field_caps_reddit_feed sat in the style guide unread for a week, so Reddit
    runs were capped and prompted as if they were Meta. The load-bearing guard
    here is that the META path is unchanged: if a Reddit branch ever leaks into
    Meta, that is a regression on the platform that actually ships today.
    """
    saved = rp._ACTIVE_PLATFORM
    try:
        rp._set_active_platform({"platform": "Meta"})
        meta = rp._feed_caps()
        rp._set_active_platform({"platform": "Reddit"})
        red = rp._feed_caps()

        check("reddit caps: body_short is 100 (Adrie's one-field spec)",
              red.get("body_short") == 100, f"got {red.get('body_short')!r}")
        check("reddit caps: body_short is the ONLY feed field",
              set(red) == {"body_short"}, str(sorted(red)))
        for gone in ("body_long", "headline_short", "headline", "description"):
            check(f"reddit caps: no {gone}", gone not in red, str(sorted(red)))
        check("reddit caps: the config's `body` key was mapped to ADAM's body_short",
              "body" not in red and "body_short" in red, str(sorted(red)))
        check("reddit caps: no leaked _note key",
              not any(k.startswith("_") for k in red), str(sorted(red)))
        check("meta caps: still the long/short pair",
              meta.get("body_long") == 300 and meta.get("body_short") == 125
              and meta.get("headline_short") == 30,
              str(sorted(meta.items())))
        check("meta caps: unchanged by the Reddit branch",
              meta == dict(rp._load_style_guide().get("field_caps_meta_feed", {})),
              "meta caps diverged from the config block")

        # The blanking pass: a model that still emits the Meta pair gets it dropped
        # on Reddit and kept on Meta.
        def _concept():
            return {"body_long": "long one", "headline_short": "short one",
                    "body_short": "keep me", "headline": "keep me too",
                    "targeting_copy": {"Prospecting": {"body_long": "aud long",
                                                       "headline_short": "aud short",
                                                       "headline": "aud headline",
                                                       "description": "aud desc",
                                                       "body_short": "aud keep"}}}
        rp._set_active_platform({"platform": "Reddit"})
        c = _concept(); rp._drop_meta_only_feed_fields(c)
        check("reddit blanking: body_long and headline_short cleared",
              c["body_long"] == "" and c["headline_short"] == "", str(c)[:90])
        _p = c["targeting_copy"]["Prospecting"]
        check("reddit blanking: per-audience feed fields all cleared",
              all(_p[f] == "" for f in ("body_long", "headline_short", "headline", "description")),
              str(_p)[:110])
        check("reddit blanking: body_short, the one field Reddit uses, survives",
              c["body_short"] == "keep me"
              and c["targeting_copy"]["Prospecting"]["body_short"] == "aud keep",
              str(c)[:90])
        check("reddit blanking: the feed headline is cleared too",
              c["headline"] == "", f"got {c['headline']!r}")
        check("reddit blanking: columns kept (blanked, not deleted)",
              "body_long" in c and "headline_short" in c)

        rp._set_active_platform({"platform": "Meta"})
        c = _concept(); rp._drop_meta_only_feed_fields(c)
        check("meta blanking: no-op on Meta",
              c["body_long"] == "long one" and c["headline_short"] == "short one",
              str(c)[:90])

        # The SCHEMA is what actually decides. A prompt saying "do not write a
        # headline" while `required` demands one produces a headline anyway —
        # that is exactly what shipped on 2026-09-15 and what Adrie filed on
        # 2026-09-21. These assert the required list itself.
        rp._set_active_platform({"platform": "Reddit"})
        rf = rp._base_fields()
        check("reddit schema: feed fields are exactly concept_tag/creative_headline/body_short/cta",
              set(rf) == {"concept_tag", "creative_headline", "body_short", "cta"}, str(sorted(rf)))
        for gone in ("headline", "headline_short", "body_long", "description"):
            check(f"reddit schema: {gone} is NOT required", gone not in rf, str(sorted(rf)))
        check("reddit schema: on-image creative_headline survives", "creative_headline" in rf)
        check("reddit schema: on-image cta survives", "cta" in rf)
        rp._set_active_platform({"platform": "Meta"})
        check("meta schema: unchanged", set(rp._base_fields()) == set(rp._BASE_FIELDS))
    finally:
        rp._ACTIVE_PLATFORM = saved


def _deliverable_checks():
    """All three deliverables must survive intake and reach the right stages.

    Adrie, 2026-09-21: an images-only Reddit order crashed at Gate 2, and a
    copy-only order could not be submitted at all and had no Reddit option.
    Two bugs, one shape: the form treated "no images" as "no creative spec",
    so it sent an empty batch list (intake rejects it outright), and the
    pipeline treated it as "no creative direction", so stage 02 returned None
    into a gate that called .get() on it.

    These assert the CONTRACT between the form's payload and intake, because
    that seam is where both failed and neither end tested it.
    """
    import importlib
    import sys as _sys
    _sys.path.insert(0, str(rp.BASE_DIR / "pipeline"))
    intake = importlib.import_module("00_intake")

    def _payload(deliverable, platform="Reddit"):
        return {
            "delivery_date": "2026-10-10", "driver": "Adrie Etherington",
            "targeting": "Prospecting", "deliverable": deliverable,
            "platform": platform,
            "batches": [{
                "platform": platform, "format": "Static Feed", "quantity": 2,
                "visual_styles": ["Testimonial"],
                "style_quantities": {"Testimonial": 2},
                "resolutions": [{"size": "1080x1350", "ratio": "4:5"}],
            }],
            "brief": "THEME: regression",
        }

    for d in ("images-copy", "images-only", "copy-only"):
        errs = intake.validate_payload(_payload(d))
        check(f"intake accepts a {d} order", not errs, "; ".join(errs))

    # The exact payload the form used to send for copy-only. Kept as a check so
    # that if anyone reinstates the empty-batches shortcut, this fails loudly
    # rather than only showing up when a requester tries to submit.
    empty = _payload("copy-only")
    empty["batches"] = []
    empty["platform"] = None
    check("intake still REJECTS the old empty-batch copy-only payload",
          bool(intake.validate_payload(empty)),
          "an empty batch list must not validate")

    co = intake.build_order(_payload("copy-only"), "t-copy-only")
    check("copy-only: includes_copy on, includes_images off",
          co["includes_copy"] is True and co["includes_images"] is False,
          f"copy={co['includes_copy']} images={co['includes_images']}")
    check("copy-only: platform survives to the order (Reddit was unreachable)",
          co["platform"] == "Reddit", repr(co["platform"]))

    io = intake.build_order(_payload("images-only"), "t-images-only")
    check("images-only: includes_images on, includes_copy off",
          io["includes_images"] is True and io["includes_copy"] is False,
          f"copy={io['includes_copy']} images={io['includes_images']}")

    # Stage 02 must no longer bail out on includes_copy=False. Concepts are the
    # sole input to stage 03's prompt/photo rows, so bailing produced zero image
    # rows AND a None that crashed the gate.
    src = (rp.BASE_DIR / "pipeline" / "run_pipeline.py").read_text()
    head = src.split("def stage_02_copy_gen", 1)[1].split("run_dir = RUNS_DIR", 1)[0]
    check("stage 02 no longer returns None for an images-only order",
          "return None" not in head, "the early-out is back")
    g2 = src.split("def resume_gate_2", 1)[1].split("def resume_gate_3", 1)[0]
    check("resume_gate_2 cannot crash on a None copy_outputs",
          "copy_outputs.get(" not in g2,
          "gate 2 dereferences copy_outputs without a guard")


def _cta_ellipsis_checks():
    """A CTA is a button: an ellipsis on one is never a legitimate trim marker.

    Adrie reported this in August across a whole style (issue #11, shipped into
    delivered files) and the exact strings still reproduced on 2026-09-22,
    because `cta` was missing from the de-ellipsis field list. CTA caps are the
    tightest in the set, so it is the field MOST likely to reach the trim.
    """
    for text, cap in (("Post a job today", 12), ("Start the search now", 12),
                      ("Find a freelancer", 10)):
        trimmed = rp._smart_trim(text, cap)
        c = {"cta": trimmed}
        rp._deellipsis_descriptions(c)
        check(f"cta: {text!r} @{cap} ships without a visible trim",
              "…" not in c["cta"] and "..." not in c["cta"],
              f"trim {trimmed!r} -> shipped {c['cta']!r}")
        check(f"cta: {text!r} @{cap} is not blanked by the clean-up",
              bool(c["cta"].strip()), f"got {c['cta']!r}")

    # Per-audience CTAs go through the same pass — a "Both" order carries its
    # real CTAs under targeting_copy, and that block was the one that shipped.
    c = {"cta": "Browse the…",
         "targeting_copy": {"Prospecting": {"cta": "Hire a…"},
                            "Retargeting": {"cta": "Post a job…"}}}
    rp._deellipsis_descriptions(c)
    offenders = [v["cta"] for v in c["targeting_copy"].values() if "…" in v["cta"]]
    check("cta: per-audience CTAs are de-ellipsised too",
          not offenders and "…" not in c["cta"], str(offenders))

    # The fields that were already covered must stay covered.
    c2 = {"creative_headline": "Hire fast…", "description": "Talent…",
          "creative_subhead": "Ready when…"}
    rp._deellipsis_descriptions(c2)
    check("on-image headline/subhead/description still de-ellipsised",
          not any("…" in v for v in c2.values()), str(c2))


def _wiki_sync_checks():
    """The Next app serves its OWN copy of the wiki, and nothing kept it in step.

    `docs/wiki/` is the source of truth, but `web/content/wiki/` is a hand-made
    duplicate that the app bundles and serves at /wiki — which is how the
    copywriter and designer actually reach these guides from inside ADAM. Every
    one of the 21 files had drifted by 2026-09-22, so the guides people read in
    the tool were not the guides in the repo. A copy with no sync check is a
    copy that is already wrong; this makes the drift fail here instead.
    """
    src_dir = rp.BASE_DIR / "docs" / "wiki"
    app_dir = rp.BASE_DIR / "web" / "content" / "wiki"
    if not app_dir.exists():
        check("wiki sync: the app's bundled wiki exists", False, str(app_dir))
        return

    src = {p.name: p.read_text() for p in sorted(src_dir.glob("*.md"))}
    app = {p.name: p.read_text() for p in sorted(app_dir.glob("*.md"))}

    missing = sorted(set(src) - set(app))
    extra = sorted(set(app) - set(src))
    drifted = sorted(n for n in (set(src) & set(app)) if src[n] != app[n])

    check("wiki sync: every source page is bundled in the app",
          not missing, f"missing from web/content/wiki: {missing}")
    check("wiki sync: the app bundles no page that left the source",
          not extra, f"orphaned in web/content/wiki: {extra}")
    check("wiki sync: no bundled page has drifted from its source",
          not drifted,
          f"{len(drifted)} drifted — run: cp docs/wiki/*.md web/content/wiki/ — {drifted}")

    # The four role guides are the ones people are sent to by name, so name them
    # individually rather than hiding them in a count.
    for slug in ("17-role-paid-acquisition", "18-role-copywriter",
                 "19-role-designer", "20-role-engineer"):
        n = f"{slug}.md"
        check(f"wiki sync: {slug} matches its source",
              n in src and n in app and src[n] == app[n],
              "drifted or missing")


def _guide_placeholder_checks():
    """A shipped guide must not tell someone to follow a link that isn't there.

    The guides carry `[LINK: ...]` markers while a real URL is still unknown.
    That is fine in a draft and not fine in the copy a new person is handed, so
    this keeps the remaining ones VISIBLE and counted rather than discovered by
    a reader. Drop the name from EXPECTED once it is filled in.
    """
    expected = {
        "17-role-paid-acquisition.md": 1,   # a recent KOTH brief — needs the team
    }
    total_open = 0
    for p in sorted((rp.BASE_DIR / "docs" / "wiki").glob("*.md")):
        n = p.read_text().count("[LINK:")
        total_open += n
        allowed = expected.get(p.name, 0)
        check(f"guide placeholders: {p.name} has {allowed} known gap(s)",
              n == allowed, f"found {n}, expected {allowed}")
    check("guide placeholders: only the KOTH brief is still unfilled",
          total_open == sum(expected.values()),
          f"{total_open} total [LINK:] markers across the wiki")


def _lead_time_checks():
    """One lead-time rule, stated in three places that had three different answers.

    On 2026-09-22 the guides said TEN business days (Lee's instruction), the
    Next order form enforced FIVE, and `order-form/order-form-local.html` — the
    one actually served at /new — enforced THREE. Nobody noticed because each
    was individually self-consistent.

    The served form is the one that binds, so it is checked first.
    """
    import re
    want = 10

    # main.py: ORDER_FORM_PATH = order-form/order-form-ravi.html. There are THREE
    # order-form HTML files here and only that one is served; the fix landed in the
    # other two first and changed nothing anyone could see. So resolve the path from
    # main.py rather than naming a file, and the test can never drift off the served
    # one again.
    mainsrc = (rp.BASE_DIR / "main.py").read_text()
    pm = re.search(r'ORDER_FORM_PATH\s*=\s*BASE_DIR\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"', mainsrc)
    check("lead time: main.py names the served order form", bool(pm), "ORDER_FORM_PATH not parseable")
    served_path = rp.BASE_DIR / pm.group(1) / pm.group(2) if pm else None
    served = served_path.read_text() if served_path and served_path.exists() else ""
    m = re.search(r"businessDaysFromToday\((\d+)\)", served)
    check(f"lead time: the SERVED form ({pm.group(2) if pm else '?'}) requires 10 business days",
          bool(m) and int(m.group(1)) == want,
          f"got {m.group(1) if m else 'no businessDaysFromToday(n)'}")
    check("lead time: the served form's on-screen hint says ten",
          "10 business days minimum" in served,
          "the hint text still shows a different number")

    nextform = (rp.BASE_DIR / "web" / "app" / "new" / "page.tsx").read_text()
    m2 = re.search(r"MIN_LEAD_BUSINESS_DAYS\s*=\s*(\d+)", nextform)
    check("lead time: the Next form agrees",
          bool(m2) and int(m2.group(1)) == want,
          f"got {m2.group(1) if m2 else 'no MIN_LEAD_BUSINESS_DAYS'}")

    guide = (rp.BASE_DIR / "docs" / "wiki" / "17-role-paid-acquisition.md").read_text()
    check("lead time: the Paid Acquisition guide says ten",
          "Ten business days out, minimum" in guide,
          "the guide no longer states the rule in the expected words")
    check("lead time: no stale '5 business days' copy survives in the guides",
          "5 business days" not in guide and "five business days" not in guide.lower(),
          "a stale lead time is still written down")


def _order_form_spec_checks():
    """Copy-only must still collect a platform and styles on the SERVED form.

    Intake rejects an empty batch list outright, so gating the batch build on
    "does this deliverable have images" meant a copy-only request could not be
    submitted at all, and Reddit — whose copy rules differ from Meta's — was
    unreachable.

    This fix landed in the WRONG FILE twice: first the Next app's page.tsx, then
    order-form-local.html. There are three order-form HTML files here and `/new`
    serves only the one main.py names. So resolve the path from main.py rather
    than hard-coding a filename, or this test drifts off the served form exactly
    the way the fix did.
    """
    mainsrc = (rp.BASE_DIR / "main.py").read_text()
    pm = re.search(r'ORDER_FORM_PATH\s*=\s*BASE_DIR\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"', mainsrc)
    if not pm:
        check("order form: main.py names the served form", False, "ORDER_FORM_PATH not parseable")
        return
    name = pm.group(2)
    served = (rp.BASE_DIR / pm.group(1) / name).read_text()

    for pattern, label in (
        ("hasImages", "a hasImages gate"),
        ("selectedDeliverable!=='copy-only'", "copy-only excluded from the spec"),
    ):
        check(f"order form ({name}): no longer has {label}",
              pattern not in served, f"found: {pattern}")
    check(f"order form ({name}): batches build whenever a platform is chosen",
          "if(selectedPlatform){" in served,
          "the platform-only gate is missing")
    check(f"order form ({name}): the platform section is never hidden by deliverable",
          "document.getElementById('platform-section').style.display = 'block';" in served,
          "the platform section is still conditionally hidden")


def _image_gen_off_checks():
    """Image generation is OFF, because generated images never reached Figma.

    The plugin's only image mechanism is applyLibraryImageToClone, which calls
    figma.getNodeByIdAsync on a node already inside the Figma file.
    plugin/code.js has no createImage, no createImageAsync, no fetch, and never
    reads the manifest's image_file / export_file columns. Measured across every
    manifest on the volume: all 312 figma_library rows and all 76 dual rows
    carry a figma_node_id; all 220 gemini_generate and all 308 text_background
    rows carry none. Every generated image was billed and then ignored.

    These assert the SWITCH, both directions, because the failure mode is
    financial and silent.
    """
    import os as _os
    prev = _os.environ.get("ADAM_ENABLE_IMAGE_GEN")
    try:
        _os.environ["ADAM_ENABLE_IMAGE_GEN"] = "0"
        rows = [{"asset_id": "a1", "generation_method": "gemini_generate", "prompt": "x"},
                {"asset_id": "a2", "generation_method": "text_background", "prompt": "y"},
                {"asset_id": "a3", "generation_method": "figma_library", "figma_node_id": "1:2"}]
        out = rp.stage_04_generate_images("regression-imggen", rows)
        check("image gen OFF: stage 04 makes no Gemini calls", out == {}, repr(out))

        # The plugin side of the same fact: if any image-loading API appears in
        # code.js, a generated image COULD reach a board and this switch should
        # be revisited rather than silently keeping spend off.
        js = (rp.BASE_DIR / "plugin" / "code.js").read_text()
        for api in ("createImageAsync", "createImage(", "fetch("):
            check(f"plugin still has no `{api}` (no path for a generated image)",
                  api not in js,
                  f"{api} appeared — the plugin may now be able to place generated images")
        check("plugin still ignores the manifest's image_file/export_file columns",
              "image_file" not in js and "export_file" not in js,
              "the plugin now reads a file column")

        # The guard must be reversible, or it is a landmine for whoever fixes this.
        _os.environ["ADAM_ENABLE_IMAGE_GEN"] = "1"
        src = (rp.BASE_DIR / "pipeline" / "run_pipeline.py").read_text()
        check("image gen switch is env-tunable in BOTH stage 03 and stage 04",
              src.count('ADAM_ENABLE_IMAGE_GEN') >= 2,
              f"found {src.count('ADAM_ENABLE_IMAGE_GEN')} reference(s)")
    finally:
        if prev is None:
            _os.environ.pop("ADAM_ENABLE_IMAGE_GEN", None)
        else:
            _os.environ["ADAM_ENABLE_IMAGE_GEN"] = prev


def offline_checks():
    print("\n== OFFLINE (deterministic) ==")
    _image_gen_off_checks()
    _lead_time_checks()
    _order_form_spec_checks()
    _audience_photo_checks()
    _reddit_copy_shape_checks()
    _deliverable_checks()
    _cta_ellipsis_checks()
    _wiki_sync_checks()
    _guide_placeholder_checks()

    # 1. Proper-noun / acronym casing backstop
    cases = [("Shipped by friday, hired monday on upwork", "Shipped by Friday, hired Monday on Upwork"),
             ("Your fractional cmo starts Monday", "Your fractional CMO starts Monday"),
             ("ai talent with real roi", "AI talent with real ROI"),
             ("Post it today. Automate it.", "Post it today. Automate it.")]  # pronoun 'it' untouched
    for a, e in cases:
        got = rp._fix_proper_nouns(a)
        check(f"casing: {a[:34]!r}", got == e, f"got {got!r}")

    # 1b. Proper-noun fixer covers per-audience bullet LISTS (2026-07-31: a
    # lowercase 'friday' shipped in a per-audience sticky bullet — lists inside
    # targeting_copy were skipped).
    _pc = {"targeting_copy": {"Retargeting": {"single_bullets": ["hired by friday"]}}}
    rp._fix_concept_proper_nouns(_pc)
    check("casing: per-audience bullet lists covered",
          _pc["targeting_copy"]["Retargeting"]["single_bullets"][0] == "hired by Friday")

    # 2. Smart trim: never dangles a comma/stopword, respects cap
    for text, cap in [("Hire the right expert today, and win", 20),
                      ("One sentence. Another sentence entirely.", 18)]:
        got = rp._smart_trim(text, cap)
        check(f"smart_trim cap {cap}", len(got) <= cap + 1 and not got.rstrip().endswith(","),
              f"got {got!r} ({len(got)})")

    # 3. Combined caps (Social columns <=65, Sticky double columns <=136)
    c1 = {"profile_left": "Full-stack developer with 8 years shipping apps",
          "profile_right": "Rated 5 stars across 40+ client projects here"}
    rp._enforce_combined_caps(c1, "Social Media Profile")
    tot = len(c1["profile_left"]) + len(c1["profile_right"])
    check("combined caps: Social <=65", tot <= 65, f"total {tot}")
    c2 = {"left_bullets": ["Post a job in minutes", "Get proposals the same day", "Hire the right pro fast"],
          "right_bullets": ["Weeks of job-board silence", "Slow recruiter back-and-forth", "Roles open for months"]}
    rp._enforce_combined_caps(c2, "Sticky Note")
    tot = sum(len(x) for x in c2["left_bullets"]) + sum(len(x) for x in c2["right_bullets"])
    check("combined caps: Sticky <=136", tot <= 136, f"total {tot}")

    # 4. Audience flatten (nested feed promotion — the Adrie empty-copy bug)
    nested = {"creative_headline": "X", "feed": {"body_short": "B", "headline": "H"}}
    flat = rp._flatten_audience(nested)
    check("flatten: nested feed promoted", flat.get("body_short") == "B" and flat.get("headline") == "H")
    check("flatten: flat passthrough", rp._flatten_audience({"body_short": "B"}).get("body_short") == "B")

    # 5. Near-dup headline detection (diverse top-N selection)
    dup_cases = [("Your new site could be live by Friday", "Your new site is converting by Friday", True),
                 ("Hired by Friday", "Hired by Friday, not next quarter", True),
                 ("Your new site could be live by Friday", "Cut the agency retainer. Keep the results.", False),
                 ("Hire smart", "In control", False),
                 ("Only pay for work you need", "You just found a way to hire for less", False)]
    for a, b, expect in dup_cases:
        check(f"near-dup: {a[:24]!r} vs {b[:24]!r}", rp._headlines_near_dup(a, b) == expect)

    # 6. 50/50 long-body parity math (even global index -> bullet, odd -> paragraph)
    bs, cps = rp._COPY_BATCH_SIZE, rp._CONCEPTS_PER_STYLE
    fmts, pos, seq = [], 0, 0
    while pos < cps:
        cnt = min(bs, cps - pos)
        fmts += ["b" if (seq * bs + j) % 2 == 0 else "p" for j in range(cnt)]
        pos += cnt
        seq += 1
    check("50/50 parity assignment", abs(fmts.count("b") - fmts.count("p")) <= 1, f"{fmts}")

    # 7. Every order-form style resolves (guide entry + caps + subhead flag)
    for s in STYLES_24:
        key, entry = rp._guide_entry_for_style(s)
        ok = entry is not None or s in NO_GUIDE_OK
        check(f"style resolves: {s}", ok, "no guide entry")
        hard, soft = rp._style_caps(s)
        check(f"style caps dict: {s}", isinstance(hard, dict) and isinstance(soft, dict))

    # 8. Intake accepts the canonical 24-style payload
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("intake", str(REPO / "pipeline" / "00_intake.py"))
    intake = ilu.module_from_spec(spec)
    spec.loader.exec_module(intake)
    payload = {"delivery_date": "2026-08-03", "driver": "regression", "targeting": "Prospecting and Retargeting",
               "deliverable": "copy-only", "brief": "x",
               "batches": [{"platform": "Meta", "format": "Static", "visual_styles": list(STYLES_24),
                            "style_quantities": {s: 1 for s in STYLES_24},
                            "resolutions": [{"size": "1440 x 1440", "ratio": "1:1"}],
                            "quantity": 1, "audience": "Both"}]}
    dup_payload = json.loads(json.dumps(payload))
    dup_payload["batches"][0]["visual_styles"] = ["Sticky Note", "Poll", "Sticky Note"]
    intake.validate_payload(dup_payload)
    check("intake dedupes duplicate styles",
          dup_payload["batches"][0]["visual_styles"] == ["Sticky Note", "Poll"],
          str(dup_payload["batches"][0]["visual_styles"]))
    errs = intake.validate_payload(payload)
    check("intake accepts 24-style payload", not errs, str(errs)[:120])

    # 8b. Placeholder-brief detection (live incident 2026-08-04: Sarah submitted
    # the order form's own template text as the brief; intake was blind to it).
    _tmpl_brief = (
        "THEME\n(One or two sentences — the single core message or angle every ad "
        "should lead with.)\n\nCOPY MUST-DOs\n- (A required phrase, claim to feature, "
        "tone note, or do/don't. Remove this line if none.)\n\nDESIGN DIRECTION\n- "
        "(A visual, style, or ad-format cue for the image stage. Remove this line if "
        "none.)\n\nRESOURCES\n- (A reference link, doc, or example asset. Remove this "
        "line if none.)"
    )
    _real_brief = (
        "THEME\nHiring shouldn't feel like a second job — show post-to-hired speed.\n\n"
        "COPY MUST-DOs\n- Use \"5-star talent\" at least once\n- No \"escrow\", say "
        "project funds\n\nDESIGN DIRECTION\n- Warm office lifestyle, not stock-y"
    )
    check("intake flags a placeholder-only brief",
          bool(intake._placeholder_brief_report(_tmpl_brief)))
    check("intake does NOT flag a real brief",
          not intake._placeholder_brief_report(_real_brief))
    check("intake does NOT flag a brief with one leftover placeholder line",
          not intake._placeholder_brief_report(
              "THEME\nSpeed to hire is the whole story.\n\nCOPY MUST-DOs\n"
              "- (A required phrase. Remove this line if none.)"))
    _pl_payload = json.loads(json.dumps(payload))
    _pl_payload["brief"] = _tmpl_brief
    _pl_payload.pop("intake_warnings", None)
    intake.validate_payload(_pl_payload)
    # 8c. Intake warnings must reach the ORDER. They were computed on the payload
    # and dropped by build_order, so no warning ever reached a human at Gate 2 —
    # including the placeholder-brief warning. The order is the agent's source.
    _warn_payload = json.loads(json.dumps(payload))
    _warn_payload["brief"] = _tmpl_brief
    _warn_payload.pop("intake_warnings", None)
    intake.validate_payload(_warn_payload)
    _built = intake.build_order(_warn_payload, "2026-08-test-warnings")
    check("build_order carries intake_warnings into the order",
          any("UNFILLED" in w for w in _built.get("intake_warnings", [])),
          str(_built.get("intake_warnings"))[:160])
    _clean_payload = json.loads(json.dumps(payload))
    _clean_payload["brief"] = _real_brief
    _clean_payload.pop("intake_warnings", None)
    intake.validate_payload(_clean_payload)
    check("a clean order carries an intake_warnings key (empty, not missing)",
          "intake_warnings" in intake.build_order(_clean_payload, "2026-08-test-clean"))

    check("placeholder brief surfaces as an intake warning",
          any("UNFILLED" in w for w in _pl_payload.get("intake_warnings", [])),
          str(_pl_payload.get("intake_warnings"))[:160])

    # 9. Craft bar contains no banned/restricted terms (the "resumes" incident)
    banned = ["resume", "vetted", "staffing", "guarantee", "manage talent", "salary"]
    bar = rp._CRAFT_BAR.lower()
    # allow mentions inside the VOCAB TRAP teaching block (quoted as what NOT to say)
    body = bar.split("vocab trap")[0]
    hits = [t for t in banned if re.search(rf"\b{t}", body)]
    check("craft bar clean of banned terms", not hits, f"found {hits}")

    # 10. Compiled refs present + key sections intact
    refs = json.loads((REPO / "configs" / "refs_context.json").read_text())
    check("refs compiled: copy_instructions", len(refs.get("copy_instructions", "")) > 5000)
    check("refs: long-body format rule present",
          "format is assigned per concept" in refs.get("copy_instructions", "").lower())
    check("refs: proper-noun day rule present",
          "days of the week" in refs.get("copy_instructions", "").lower())

    # 11a. SCHEMA COVERS EVERY PROMPTED FIELD (audit 2026-07-30: Poll's integer
    # percentages had no char_limits entry, so additionalProperties:false
    # stripped them from every Poll concept since structured output landed).
    # Mirror of the multi_field branches in _generate_copy_for_style, keyed by
    # the same _sl normalization.
    _schema_missing = []
    _schema_optional = []
    for _style in STYLES_24:
        _fields = EXTRAS_BY_SL.get(_style.strip().lower().replace(" ", ""), [])
        if not _fields:
            continue
        _item = rp._concept_schema(_style, False, 6)["properties"]["concepts"]["items"]
        _props, _req = _item["properties"], _item["required"]
        _schema_missing += [f"{_style}:{f}" for f in _fields if f not in _props]
        # Optional extras under additionalProperties:false = the model may
        # legally omit the fields that ARE the ad (live incident 2026-07-30).
        _schema_optional += [f"{_style}:{f}" for f in _fields
                             if f in _props and f not in _req]
    check("schema declares every prompted style field", not _schema_missing,
          str(_schema_missing))
    check("schema REQUIRES every prompted style field", not _schema_optional,
          str(_schema_optional))
    # Per-audience extras (Logan 2026-07-31): P&R audience blocks must REQUIRE
    # the style's own on-image fields — they were generated once and shared,
    # so Retargeting creatives printed Prospecting's copy.
    _aud_missing = []
    for _style in STYLES_24:
        _fields = EXTRAS_BY_SL.get(_style.strip().lower().replace(" ", ""), [])
        if not _fields:
            continue
        _aud = (rp._concept_schema(_style, True, 6)["properties"]["concepts"]["items"]
                ["properties"]["targeting_copy"]["properties"]["Prospecting"])
        _aud_missing += [f"{_style}:{f}" for f in _fields
                         if f not in _aud["properties"] or f not in _aud["required"]]
    check("schema REQUIRES style fields PER AUDIENCE", not _aud_missing, str(_aud_missing))

    # 11b. Fail-closed selection: _deterministic_selection enforces legal/caps
    # even when review never ranked (the API-failure fallback path).
    _fc = [
        {"headline": "Clean one", "creative_headline": "Ship it this week",
         "rank": 0, "selected": True},
        {"headline": "Illegal one", "creative_headline": "Vetted talent now",
         "rank": 0, "selected": True, "legal_flags": ["vetted"]},
        {"headline": "Clean two", "creative_headline": "Proposals by Tuesday",
         "rank": 0, "selected": True},
        {"headline": "Overflow", "creative_headline": "Way over the template cap",
         "rank": 0, "selected": True, "length_flags": ["creative_headline 90>65"]},
    ]
    rp._deterministic_selection(_fc, 2, "test-style")
    check("fail-closed: legal-flagged never selected", not _fc[1]["selected"],
          "legal concept survived selection")
    check("fail-closed: selection floor respected",
          sum(1 for c in _fc if c["selected"]) == 2,
          f"{sum(1 for c in _fc if c['selected'])} selected, wanted 2")
    check("fail-closed: clean concepts win over flagged",
          _fc[0]["selected"] and _fc[2]["selected"],
          "flagged concept selected ahead of a clean one")

    # 11d. No-AI-photography policy: photo-library styles are module-level and
    # the policy set must contain the people styles (audit 2026-07-30 — a
    # library outage used to reroute these into Gemini person-prompts).
    check("photo policy: people styles in PHOTO_LIBRARY_STYLES",
          {"Lifestyle Photo", "Photo with Text", "Testimonial"} <= rp.PHOTO_LIBRARY_STYLES,
          str(rp.PHOTO_LIBRARY_STYLES))
    _src_rp = (REPO / "pipeline" / "run_pipeline.py").read_text()
    check("photo policy: assertion marker present in stage 03",
          "blocked_ai_people_photo" in _src_rp)
    # 2026-07-31: both post-hoc guards were DEAD CODE for a day — they read
    # row["method"] while the real column is generation_method, and the unit
    # test used the same wrong key. Guards must reference the real column.
    check("photo policy + veto guards use the real column name",
          'row.get("method")' not in _src_rp and '_row.get("method")' not in _src_rp)

    # 11f. AUTHORITY REGISTRY (Logan's slider concept, 2026-07-30): every model
    # task carries a declared authority level; the prompt section and the human
    # doc are generated from authority.py and must not drift; every function a
    # registry row names as source-of-truth or fence must actually exist.
    import authority
    _aerrs = authority.validate()
    check("authority: registry invariants hold", not _aerrs, "; ".join(_aerrs))
    _doc = (REPO / "docs" / "AUTHORITY.md")
    check("authority: docs/AUTHORITY.md in sync (run python3 authority.py)",
          _doc.exists() and _doc.read_text() == authority.render_markdown())
    _orch_src = (REPO / "agent" / "orchestrator.py").read_text()
    check("authority: prompt section wired into the agent",
          "render_prompt_section" in _orch_src)
    _rp_src = (REPO / "pipeline" / "run_pipeline.py").read_text()
    _missing_refs = []
    for _t in authority.TASKS:
        for _txt in (_t.get("source") or "", _t.get("validators") or ""):
            for _name in re.findall(r"\b(tool_[a-z_]+|_[a-z_]{3,})\b", _txt):
                if _name not in _orch_src and _name not in _rp_src:
                    _missing_refs.append(f"{_t['task'][:30]}→{_name}")
    check("authority: every named source/fence exists in code", not _missing_refs,
          str(_missing_refs))
    _rendered = authority.render_prompt_section()
    check("authority: all six surfaces render",
          all(s in _rendered for s in ("Gate 2", "Gate 3", "Gate 4", "Gate 5", "Gate 6", "Chat")))

    # 11g. Cross-style concept-tag uniqueness (2026-07-31: two styles invented
    # 'budget-control-v1' independently; the Figma plugin groups boards by tag
    # and folded both concepts into one — 11 boards for 12 concepts).
    _tc = [{"concept_tag": "a"}, {"concept_tag": "a"}, {"concept_tag": "a"}, {"concept_tag": "b"}]
    rp._dedupe_concept_tags(_tc)
    _tags = [c["concept_tag"] for c in _tc]
    check("concept tags de-duped cross-style", len(_tags) == len(set(_tags)), str(_tags))
    check("tag de-dup wired at collection point",
          "_dedupe_concept_tags(reviewed_concepts)" in (REPO / "pipeline" / "run_pipeline.py").read_text())

    # 11e. Registry slot caps must not crush auxiliary fields on styles that
    # define their OWN on-image field set (Sticky's 12-char "Hire it…" trims,
    # live incident 2026-07-30). Styles where creative_headline IS the printed
    # field must KEEP their registry caps.
    _sh, _ = rp._style_caps("Sticky Note")
    check("sticky: creative_headline not slot-capped", "creative_headline" not in _sh,
          f"hard caps: {_sh}")
    _lh, _ = rp._style_caps("Lifestyle Photo")
    check("lifestyle: registry cap still applies",
          isinstance(_lh.get("creative_headline"), int), f"hard caps: {_lh}")

    # 11c. sprint_state: atomic CAS gate claims (audit 2026-07-30 — three
    # approval surfaces used to race; now exactly one claimer can win).
    import threading as _th
    import sprint_state as _ss
    _sd = SCRATCH / "state_test_sprint"
    _sd.mkdir(exist_ok=True)
    _ss.write_state(_sd, {"state": "awaiting_gate_3"})
    _wins = []
    def _try_claim():
        won, _ = _ss.claim_gate(_sd, 3)
        if won:
            _wins.append(1)
    _threads = [_th.Thread(target=_try_claim) for _ in range(8)]
    [t.start() for t in _threads]
    [t.join() for t in _threads]
    check("sprint_state: exactly one concurrent claimer wins", len(_wins) == 1,
          f"{len(_wins)} winners out of 8 racers")
    check("sprint_state: claimed state is resuming",
          _ss.read_state(_sd).get("state") == "resuming_gate_3")
    _won2, _prior2 = _ss.claim_gate(_sd, 3)
    check("sprint_state: second claim loses with prior state",
          not _won2 and _prior2 == "resuming_gate_3", f"won={_won2} prior={_prior2}")
    (_sd / "pipeline_state.json").write_text('{"state": "awaiting_ga')  # torn write
    _cor = _ss.read_state(_sd)
    check("sprint_state: torn file reads as visible corrupt state",
          _cor.get("state") == "corrupt" and "error" in _cor, str(_cor))
    _ss.write_state(_sd, {"state": "error", "failed_gate": 4})
    check("sprint_state: atomic write recovers over torn file",
          _ss.read_state(_sd).get("failed_gate") == 4)

    # 11. NO SILENT REF TRUNCATION (2026-07-30 audit: fixed [:N] slices were cutting
    # 40-91% of the reference docs — Adrie's examples lost 91%, the legal blocklist
    # was amputated mid-sentence). Ratchet: any `var[:N]` slice in run_pipeline.py
    # on a ref-doc variable must either cover the doc's full current length or be
    # on the explicit allowlist of intentional context slices.
    src = "\n".join(l for l in (REPO / "pipeline" / "run_pipeline.py")
                    .read_text().splitlines() if not l.lstrip().startswith("#"))
    ref_vars = {
        "copy_instructions": "copy_instructions", "brand_voice": "brand_voice",
        "writing_style": "writing_style", "compliance": "compliance",
        "playbook": "playbook", "claims": "claims", "copy_bank": "copy_bank",
        "copy_style_rules": "copy_style_rules",
        "_prosp_ex": "prospecting_examples", "_retarget_ex": "retargeting_examples",
        "examples": None,  # max of both example docs
    }
    allowed = {("compliance", 4000),        # judge context; legal is enforced post-hoc
               ("copy_style_rules", 4000)}  # judge fallback when no entry matched
    bad = []
    for var, cap_s in re.findall(r"\b(\w+)\[:(\d+)\]", src):
        if var not in ref_vars:
            continue
        cap = int(cap_s)
        if (var, cap) in allowed:
            continue
        key = ref_vars[var]
        n = (max(len(str(refs.get("prospecting_examples") or "")),
                 len(str(refs.get("retargeting_examples") or "")))
             if key is None else len(str(refs.get(key) or "")))
        if n > cap:
            bad.append(f"{var}[:{cap}] loses {n - cap} of {n} chars")
    check("no ref doc silently truncated in prompts", not bad, "; ".join(bad))


def live_checks(all_styles=False):
    print("\n== LIVE (real copy generation — costs API $) ==")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        check("live: ANTHROPIC_API_KEY present", False, "run via `railway run --service adam -- …`")
        return
    styles = STYLES_24 if all_styles else ["Notification", "Talent Profile", "Tweet / Post Mockup",
                                           "Poll", "Sticky Note", "Chat Bubble"]
    brief = ("Sprint 10 THEME: Outcome Alignment. Highlight specific project outcomes with "
             "freelancers (launch a high-converting site, scale paid ads, chatbot support, "
             "standout brand, workflow automation, sales pipeline). Angle: businesses need to "
             "know what Upwork can do for them. Lean into faster-than-competitors language.")
    payload = {"delivery_date": "2026-08-03", "driver": "regression-live", "targeting": "Prospecting and Retargeting",
               "deliverable": "copy-only", "brief": brief,
               "batches": [{"platform": "Meta", "format": "Static", "visual_styles": list(styles),
                            "style_quantities": {s: 1 for s in styles},
                            "resolutions": [{"size": "1440 x 1440", "ratio": "1:1"}],
                            "quantity": 1, "audience": "Both"}]}
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sid = rp.run_full_pipeline(payload)
        rp.resume_gate_2(sid)
    co = json.loads((Path(os.environ["RUNS_DIR"]) / sid / "copy_outputs.json").read_text())
    cs = co["concepts"]

    def norm(s):
        return re.sub(r"[^a-z0-9]+", "", str(s).lower())

    check("live: no failed styles", not co.get("failed_styles"), str(co.get("failed_styles")))
    for s in styles:
        sel = [c for c in cs if norm(c.get("visual_style")) == norm(s) and c.get("selected")]
        p = sum(1 for c in sel if rp._flatten_audience((c.get("targeting_copy") or {}).get("Prospecting") or {}).get("body_short"))
        r = sum(1 for c in sel if rp._flatten_audience((c.get("targeting_copy") or {}).get("Retargeting") or {}).get("body_short"))
        oc = sum(1 for c in sel if str(c.get("creative_headline") or "").strip())
        _extras = EXTRAS_BY_SL.get(s.strip().lower().replace(" ", ""), [])
        if _extras:
            _missing_ex = [f"{c.get('concept_id')}:{f}" for c in sel for f in _extras
                           if c.get(f) in (None, "", [])]
            check(f"live extras present: {s}", not _missing_ex, str(_missing_ex[:4]))
            _aud_missing_ex = []
            for c in sel:
                for _an, _ab in (c.get("targeting_copy") or {}).items():
                    if isinstance(_ab, dict):
                        _aud_missing_ex += [f"{c.get('concept_id')}.{_an}:{f}"
                                            for f in _extras if _ab.get(f) in (None, "", [])]
            check(f"live extras present PER AUDIENCE: {s}", not _aud_missing_ex,
                  str(_aud_missing_ex[:4]))
        hl = sum(1 for c in sel if str(c.get("headline") or "").strip() and str(c.get("headline_short") or "").strip())
        check(f"live spec: {s}", len(sel) >= 2 and p >= 2 and r >= 2 and oc == len(sel) and hl == len(sel),
              f"sel={len(sel)} P={p} R={r} oc={oc} hl={hl}")
        # diverse choices: the selected pair must not be near-dups
        if len(sel) >= 2:
            a, b = (sel[0].get("creative_headline") or "", sel[1].get("creative_headline") or "")
            check(f"live diverse picks: {s}", not rp._headlines_near_dup(a, b), f"{a!r} vs {b!r}")
        # Poll percentages must ARRIVE (audit 2026-07-30: the schema stripped
        # them for every Poll sprint since structured output landed).
        if s.strip().lower().replace(" ", "") == "poll":
            _nopct = [c.get("concept_id") for c in sel
                      if not (isinstance(c.get("poll_pct_a"), int)
                              and isinstance(c.get("poll_pct_b"), int))]
            check("live: poll percentages present", not _nopct, str(_nopct))
    bl = [c.get("body_long") for c in cs if c.get("body_long")]
    nb = sum(1 for t in bl if re.search(r"\n\s*([^\w\s]|[-•*])", str(t)))
    check("live: ~50/50 long-body split", bl and 0.35 <= nb / len(bl) <= 0.65, f"{nb}/{len(bl)} bulleted")
    # Bulleted bodies must OPEN with a lead-in sentence, never a bare bullet
    # (Adrie 2026-07-29: "just the bullet points with no copy before it").
    bare = [t for t in bl if re.match(r"\s*[^\w\s]", str(t).strip())]
    def _descs(c):
        # Every displayed single-line field, base + per-audience — a visible
        # trim on an ON-IMAGE line shipped live 2026-07-31 ('Skilled pros, right…').
        tc = c.get("targeting_copy") or {}
        fields = ("description", "creative_headline", "creative_subhead")
        out = [c.get(f) for f in fields]
        for a in tc.values():
            if isinstance(a, dict):
                out += [a.get(f) for f in fields]
        return out
    ell = [d for c in cs if c.get("selected") for d in _descs(c)
           if str(d or "").rstrip().endswith(("…", "..."))]
    check("live: no ellipsis-trimmed descriptions", not ell, str(ell[:2]))
    check("live: bulleted bodies have a lead-in", not bare,
          f"{len(bare)} start with a bullet: {str(bare[0])[:60]!r}" if bare else "")
    blob = " ".join(json.dumps(c) for c in cs if c.get("selected"))
    lows = re.findall(r"\b(monday|tuesday|wednesday|thursday|friday|cfo|cmo|roi|upwork)\b", blob)
    check("live: casing clean in selected copy", not lows, f"lowercase hits {set(lows)}")
    flagged = sum(1 for c in cs if c.get("legal_flags") and c.get("selected"))
    check("live: no legal-flagged concept selected", flagged == 0, f"{flagged} selected with flags")
    tu = json.loads((Path(os.environ["RUNS_DIR"]) / sid / "token_usage.json").read_text())
    print(f"  (live run cost: ${tu.get('estimated_cost_usd')})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run a real copy generation (costs $)")
    ap.add_argument("--all", action="store_true", help="live mode covers all 24 styles (~$2-3)")
    args = ap.parse_args()
    print(f"ADAM copy regression · scratch={SCRATCH}")
    offline_checks()
    if args.live:
        live_checks(all_styles=args.all)
    print(f"\n{'PASS — all checks green' if not FAILURES else 'FAIL — ' + str(len(FAILURES)) + ' failure(s):'}")
    for f in FAILURES:
        print("  ✗", f)
    sys.exit(1 if FAILURES else 0)
