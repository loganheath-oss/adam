"""
test_new_styles_routing.py
==========================
Smoke test for the May 2026 Path B changes: confirms that orders containing
"Text with Button" and "Notification" pass intake validation AND route through
the correct image-generation paths (library photo vs Gemini vs background-only).

No API calls. No cost. Run in ~1 second.

    python3 pipeline/test_new_styles_routing.py
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE = REPO_ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fail(msg: str):
    print(f"  ✗ FAIL: {msg}")
    sys.exit(1)


def ok(msg: str):
    print(f"  ✓ {msg}")


def main():
    print("\n=== Path B routing smoke test ===\n")

    # ── 1. Intake validation accepts both new styles
    intake = load_module("intake", PIPELINE / "00_intake.py")

    sample_payload = {
        "delivery_date": "2026-05-08",
        "driver": "Path B Smoke Test",
        "targeting": "Prospecting",
        "deliverable": "images-copy",
        "brief": "Routing test",
        "batches": [{
            "platform": "Meta",
            "format": "Static",
            "quantity": 4,
            "visual_styles": [
                "Lifestyle Photo",     # baseline (already worked)
                "Notification",        # newly photo-based
                "Text with Button",    # canonical name
                "Text with Button and Cursor",  # legacy alias still accepted
            ],
            "resolutions": [
                {"size": "1440x1440", "ratio": "1:1"},
                {"size": "1440x1800", "ratio": "4:5"},
            ],
        }],
    }

    print("Intake validation:")
    errors = intake.validate_payload(sample_payload)
    if errors:
        fail(f"validate_payload returned errors: {errors}")
    ok("payload with all four styles passes validation")

    # ── 2. figma_library routes Notification through the photo library
    figma_library = load_module("figma_library", PIPELINE / "figma_library.py")

    print("\nfigma_library routing:")
    if "Notification" in figma_library.NON_PHOTO_STYLES:
        fail("Notification still in NON_PHOTO_STYLES (should be photo-based)")
    ok("Notification removed from NON_PHOTO_STYLES")

    if figma_library.VISUAL_STYLE_TO_TAG.get("Notification") != "lifestyle_photo":
        fail(f"Notification → tag should be 'lifestyle_photo', got {figma_library.VISUAL_STYLE_TO_TAG.get('Notification')!r}")
    ok("Notification maps to style_fit tag 'lifestyle_photo'")

    if "Text with Button" not in figma_library.NON_PHOTO_STYLES:
        fail("Text with Button missing from NON_PHOTO_STYLES")
    ok("Text with Button correctly in NON_PHOTO_STYLES (no library lookup)")

    # ── 3. pick_photo_for_asset returns the right shape per style
    print("\npick_photo_for_asset routing decisions:")

    # Notification → should attempt library lookup (returns is_photo_based=True
    # even if no candidates match, so we use a mock library to confirm the path).
    mock_lib = figma_library._enrich_mock(figma_library.MOCK_COMPONENTS)
    notif_result = figma_library.pick_photo_for_asset(
        "Notification", {"targeting": "Prospecting"}, "smoketest", components=mock_lib
    )
    if not notif_result.get("is_photo_based"):
        fail(f"Notification should be photo-based, got {notif_result}")
    ok(f"Notification → photo-based ({notif_result.get('match_strength','?')} match)")

    # Text with Button → should NOT be photo-based (skips library entirely)
    twb_result = figma_library.pick_photo_for_asset(
        "Text with Button", {"targeting": "Prospecting"}, "smoketest", components=mock_lib
    )
    if twb_result.get("is_photo_based"):
        fail(f"Text with Button should NOT be photo-based, got {twb_result}")
    ok("Text with Button → non-photo (skips library, goes to Gemini/background)")

    # Legacy "Text with Button and Cursor" should also be non-photo
    twb_legacy = figma_library.pick_photo_for_asset(
        "Text with Button and Cursor", {"targeting": "Prospecting"}, "smoketest", components=mock_lib
    )
    if twb_legacy.get("is_photo_based"):
        fail(f"Text with Button and Cursor should NOT be photo-based, got {twb_legacy}")
    ok("Text with Button and Cursor (legacy) → non-photo")

    # ── 4. MCP server normalization (extract dict via AST; avoid importing
    #      mcp_server/server.py which depends on the fastmcp package in .venv)
    print("\nMCP server normalization:")
    import ast
    server_src = (REPO_ROOT / "mcp_server" / "server.py").read_text()
    tree = ast.parse(server_src)
    norm_dict = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VISUAL_STYLE_NORMALIZATION":
                    norm_dict = ast.literal_eval(node.value)
    if not norm_dict:
        fail("VISUAL_STYLE_NORMALIZATION not found in mcp_server/server.py")

    if norm_dict.get("Text with Button and Cursor") != "Text with Button":
        fail(f"missing Text with Button and Cursor → Text with Button entry. Current dict: {norm_dict}")
    ok("MCP normalizes 'Text with Button and Cursor' → 'Text with Button'")

    print("\n✓ All routing checks passed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
