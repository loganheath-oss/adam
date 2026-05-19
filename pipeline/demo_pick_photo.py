"""
demo_pick_photo.py — Simulates an order and shows which photo the pipeline would pick.

Run with:
    SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())") \
    FIGMA_ACCESS_TOKEN='figd_...' \
    python3 pipeline/demo_pick_photo.py
"""

import sys
import os

# Add the pipeline directory so we can import figma_library
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from figma_library import (
    fetch_library_components,
    pick_photo_for_asset,
    VISUAL_STYLE_TO_TAG,
)


def run_demo():
    print("=" * 70)
    print("  ADAM PIPELINE — IMAGE SELECTION DEMO")
    print("=" * 70)

    # Simulated order
    order = {
        "sprint_id":     "demo-2026-04-meta-9999",
        "driver":        "Logan Heath",
        "targeting":     "Prospecting",
        "brief":         "Showcase how Upwork helps small businesses hire skilled freelancers fast.",
        "platform":      "Meta",
        "delivery_date": "2026-05-01",
    }

    print(f"\nSimulated order:")
    for k, v in order.items():
        print(f"  {k:<14} {v}")

    print(f"\n→ Fetching library from Figma (one-time, then cached for the demo)...")
    components = fetch_library_components()
    print(f"  Library contains {len(components)} tagged components")

    # Try each visual style
    for visual_style in ["Lifestyle Photo", "Photo with Text", "Testimonial"]:
        print()
        print("-" * 70)
        print(f"  Visual style requested: {visual_style}")
        print("-" * 70)

        result = pick_photo_for_asset(
            visual_style=visual_style,
            order=order,
            sprint_id=order["sprint_id"],
            components=components,  # reuse fetched library
        )

        if not result.get("is_photo_based"):
            print(f"  → Skipped (not a photo-based style)")
            continue

        if result.get("needs_human_selection"):
            print(f"  → No matches found — would flag for human selection.")
            print(f"     Required tags: {result.get('required_tags')}")
            continue

        print(f"  ✓ SELECTED PHOTO")
        print(f"     Name:           {result['figma_asset_name']}")
        print(f"     node_id:        {result['figma_asset_id']}")
        print(f"     Match strength: {result['match_strength']}")
        print(f"     Tags I asked for:    {result.get('required_tags')}")
        print(f"     Tags that matched:   {result.get('matched_tags_used')}")
        print(f"     Photo's actual tags: {result.get('photo_tags')}")

        # Build a Figma URL so user can click to view the picked photo
        figma_file_id = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")
        node_id_url = result["figma_asset_id"].replace(":", "-")
        figma_url = f"https://www.figma.com/design/{figma_file_id}?node-id={node_id_url}"
        print(f"     View in Figma:  {figma_url}")

    print()
    print("=" * 70)
    print("  Demo complete. The pipeline can now pull library photos by tag query.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
