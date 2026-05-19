"""
figma_library.py
================
Figma photo library integration for the ADAM pipeline.

Pulls tagged photos from the Upwork brand photography library in Figma based
on a visual style and order context. Follows Brian's rule: no AI-generated
photography — all people photos come from the approved library.

Tagging format (Brandon's approach):
    Each photo is a Figma component. Inside the component, invisible
    rectangles act as tags — the rectangle's LAYER NAME is the tag.
    Rectangles must have visible=false (hidden) to be recognized.

    Example component structure:
        Photo_001 (component)
          ├─ [visible image layer]
          ├─ man_1              (hidden rectangle — tag)
          ├─ laptop             (hidden rectangle — tag)
          ├─ warm               (hidden rectangle — tag)
          ├─ home_office        (hidden rectangle — tag)
          ├─ lifestyle_photo    (hidden rectangle — tag)
          └─ rights_2026_01     (hidden rectangle — expiration)

Tag taxonomy is flat — Brandon writes `man_1`, not `people-man_1`. The code
groups tags by dimension via TAG_REGISTRY.

Usage:
    from figma_library import pick_photo_for_asset

    photo = pick_photo_for_asset(
        visual_style="Lifestyle Photo",
        order={...},
        sprint_id="2026-04-meta-a3f2",
    )

Standalone testing:
    python3 figma_library.py --test           # mock data, no API call
    python3 figma_library.py --list           # fetch + list all components + their tags
    python3 figma_library.py --find <tags>    # find matches for a comma-separated tag list
"""

import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Python 3.14 on macOS python.org installer ships without root CAs in the
# system default context. Use certifi when available so requests to
# api.figma.com work locally as well as on Fly.
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

# ── CONFIG ────────────────────────────────────────────────────────────────────

FIGMA_API_BASE      = "https://api.figma.com/v1"
FIGMA_ACCESS_TOKEN  = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FIGMA_FILE_ID       = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")

# Where recently-used photo IDs are tracked (to avoid repeats across sprints)
HISTORY_FILE        = Path(__file__).parent.parent / "runs" / "_library_history.json"
RECENT_SPRINT_COUNT = 3

# Rights expiration tag pattern: `rights_YYYY_MM`
RIGHTS_PATTERN = re.compile(r"^rights_(\d{4})_(\d{2})$")

# People actor pattern: `man_1`, `woman_7`, etc. Each number = a unique actor.
PEOPLE_PATTERN = re.compile(r"^(man|woman)_(\d+)$")


# ── TAG REGISTRY ──────────────────────────────────────────────────────────────
# Maps each flat tag to its semantic dimension.
# Brandon uses the tags on the left; code organizes them via the dimension on
# the right. Priority drives progressive fallback order:
#   1 = never drop  (style)
#   2 = drop last   (people, presence)
#   3 = drop middle (objects, setting)
#   4 = drop earlier (demographics, age)
#   5 = drop first  (palette, mood, activity, composition)

DIMENSION_PRIORITY = {
    "style":        1,
    "people":       2,
    "objects":      3,
    "setting":      3,
    "demographics": 4,
    "age":          4,
    "palette":      5,
    "mood":         5,
    "activity":     5,
    "composition":  5,
}

TAG_REGISTRY: dict[str, str] = {
    # style (which template this photo fits) — priority 1
    "lifestyle_photo":   "style",
    "photo_with_text":   "style",
    "testimonial":       "style",

    # people special-case tags — priority 2
    # Individual actor tags like `man_3`, `woman_7` are matched via PEOPLE_PATTERN
    # in tag_dimension(), so they don't need to be listed here.
    "team":       "people",
    "hands_only": "people",
    "none":       "people",  # photo has no people (e.g. environment-only)

    # objects (what's visible) — priority 3
    "laptop":          "objects",
    "phone":           "objects",
    "tablet":          "objects",
    "desktop_monitor": "objects",
    "headphones":      "objects",
    "notebook":        "objects",
    "pen":             "objects",
    "coffee":          "objects",
    "plant":           "objects",
    "whiteboard":      "objects",
    "camera":          "objects",
    "book":            "objects",
    "document":        "objects",

    # setting (location) — priority 3
    "home_office":      "setting",
    "corporate_office": "setting",
    "coworking":        "setting",
    "coffee_shop":      "setting",
    "outdoor":          "setting",
    "studio":           "setting",
    "kitchen":          "setting",
    "bookstore":        "setting",
    "greenhouse":       "setting",
    "retail":           "setting",
    "hotel":            "setting",
    "warehouse":        "setting",

    # demographics (applied per-person shown) — priority 4
    "asian":       "demographics",
    "south_asian": "demographics",
    "black":       "demographics",
    "latino":      "demographics",
    "white":       "demographics",
    "mixed":       "demographics",

    # age — priority 4
    "young_adult": "age",
    "adult":       "age",
    "mature":      "age",

    # palette — priority 5
    "warm":         "palette",
    "cool":         "palette",
    "neutral":      "palette",
    "green":        "palette",
    "dark":         "palette",
    "bright":       "palette",
    "upwork_green": "palette",

    # mood — priority 5
    "focused":       "mood",
    "confident":     "mood",
    "happy":         "mood",
    "contemplative": "mood",
    "surprised":     "mood",

    # activity — priority 5
    "typing":         "activity",
    "on_phone":       "activity",
    "on_call":        "activity",
    "meeting":        "activity",
    "thinking":       "activity",
    "presenting":     "activity",
    "holding_coffee": "activity",
    "holding_object": "activity",
    "walking":        "activity",
    "standing":       "activity",
    "gesturing":      "activity",
    "facing_camera":  "activity",
    "working":        "activity",
    "browsing":       "activity",
    "reading":        "activity",
    "writing":        "activity",
    "listening":      "activity",
    "drawing":        "activity",
    "waving":         "activity",
    "sitting":        "activity",

    # composition — priority 5
    "centered":       "composition",
    "left_of_frame":  "composition",
    "right_of_frame": "composition",
    "close_up":       "composition",
    "medium_shot":    "composition",
    "wide_shot":      "composition",
}


def tag_dimension(tag: str) -> Optional[str]:
    """Return the semantic dimension for a tag, or None if unknown."""
    if RIGHTS_PATTERN.match(tag):
        return "rights"
    if PEOPLE_PATTERN.match(tag):
        return "people"
    return TAG_REGISTRY.get(tag)


def gender_of(tag: str) -> Optional[str]:
    """Return 'man' or 'woman' for actor tags like 'man_3', else None."""
    m = PEOPLE_PATTERN.match(tag)
    return m.group(1) if m else None


def photo_has_gender(tags: list[str], gender: str) -> bool:
    """True if any actor tag in the photo matches the given gender ('man' or 'woman')."""
    return any(gender_of(t) == gender for t in tags)


# ── NAMED VISUAL STYLE → REQUIRED STYLE TAG ──────────────────────────────────
# Maps the user-facing visual_style (from the order form) to the style tag.

VISUAL_STYLE_TO_TAG = {
    "Lifestyle Photo":   "lifestyle_photo",
    "Photo with Text":   "photo_with_text",
    "Testimonial":       "testimonial",
    # Notification cards embed a small portrait/upper-body person shot. Library
    # photos tagged lifestyle_photo work well as the source — they're person-
    # in-context shots that crop cleanly into the notification template's
    # image slot.
    "Notification":      "lifestyle_photo",
    # Split Screen pulls TWO library photos (one per placeholder). Both come
    # from the lifestyle_photo pool. Caller is responsible for invoking
    # pick_photo_for_asset twice with exclude_ids to guarantee distinct picks.
    "Split Screen":      "lifestyle_photo",
    # Aliases for styles that reuse a photo template
    "Social Media Profile": "testimonial",
    "Talent Profile":       "testimonial",
}

# Styles that don't use the photo library — fall through to Gemini generation.
# Notification was here previously; it's now photo-based (the Figma template
# has a photo slot we want filled from the library for diversity).
NON_PHOTO_STYLES = {
    "Text Only", "Chat Bubble", "Reminder", "Poll",
    "Tweet / Post Mockup", "Graphic with Text", "Pie Chart",
    "Search Results", "Search Bar with Talent Badge",
    "Text with Button", "Text with Button and Cursor",
    "Illustration", "Text Based",
}


# ── FIGMA API CLIENT ──────────────────────────────────────────────────────────

def _figma_request(path: str, timeout: int = 30) -> dict:
    """Make an authenticated GET request to the Figma API."""
    if not FIGMA_ACCESS_TOKEN:
        raise EnvironmentError(
            "FIGMA_ACCESS_TOKEN is not set. Export it first:\n"
            "  export FIGMA_ACCESS_TOKEN='figd_...'"
        )
    url = f"{FIGMA_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={"X-Figma-Token": FIGMA_ACCESS_TOKEN},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── TAG PARSING FROM COMPONENT CHILDREN ───────────────────────────────────────

def _collect_hidden_rect_names(node: dict) -> list[str]:
    """Recursively walk a Figma node tree, returning the names of every hidden rectangle.

    Hidden rectangles (visible=false) are how Brandon encodes tags. Every other
    node type and every visible rectangle is ignored.
    """
    names: list[str] = []

    if node.get("type") == "RECTANGLE" and node.get("visible") is False:
        name = node.get("name", "").strip()
        if name:
            names.append(name)

    for child in node.get("children", []) or []:
        names.extend(_collect_hidden_rect_names(child))

    return names


def _rights_are_valid(tags: list[str], now: Optional[datetime] = None) -> bool:
    """Return False if any `rights_YYYY_MM` tag has expired."""
    now = now or datetime.now(timezone.utc)
    for tag in tags:
        m = RIGHTS_PATTERN.match(tag)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            # Rights expire at the END of the named month
            expiry_year, expiry_month = (year + 1, 1) if month == 12 else (year, month + 1)
            expiry = datetime(expiry_year, expiry_month, 1, tzinfo=timezone.utc)
            if now >= expiry:
                return False
    return True


def group_tags_by_dimension(tags: list[str]) -> dict[str, list[str]]:
    """Group a flat tag list by their semantic dimensions."""
    grouped: dict[str, list[str]] = {}
    for tag in tags:
        dim = tag_dimension(tag)
        if dim is None:
            grouped.setdefault("unknown", []).append(tag)
        else:
            grouped.setdefault(dim, []).append(tag)
    return grouped


# ── LIBRARY FETCH ─────────────────────────────────────────────────────────────

def fetch_library_components(file_id: Optional[str] = None) -> list[dict]:
    """Fetch all tagged photo nodes from the Figma file (frames or components).

    Walks the entire file tree. Considers any node a "tagged photo" if it has
    BOTH an image-bearing descendant AND at least 3 hidden tag-eligible
    descendants whose names match the tag registry. This works whether the
    tagged photos are stored as components or frames.

    Returns list of dicts:
        {
            "node_id":       "1234:567",
            "name":          "coding_together_03",
            "thumbnail_url": "",
            "tags":          ["man_1", "laptop", "warm", "lifestyle_photo"],
            "tags_by_dim":   {"people": ["man_1"], "objects": ["laptop"], ...},
            "rights_valid":  True,
        }
    """
    fid = file_id or FIGMA_FILE_ID

    # Fetch full file tree in one call
    file_data = _figma_request(f"/files/{fid}")
    document = file_data.get("document", {})

    found: list[dict] = []
    _walk_for_tagged_photos(document, found)
    return found


def _walk_for_tagged_photos(node: dict, results: list[dict]) -> None:
    """Recursively walk the document tree, looking for tagged photo nodes.

    A node is considered a "tagged photo" if it is a FRAME/COMPONENT/INSTANCE that
    has BOTH (a) an image-bearing DIRECT child and (b) at least 3 recognized
    hidden tag-eligible DIRECT children. This identifies the leaf-level photo
    nodes, not their parent containers.
    """
    if not isinstance(node, dict):
        return

    if _is_tagged_photo_node(node):
        tags = _collect_direct_hidden_tag_names(node)
        results.append({
            "node_id":       node.get("id", ""),
            "name":          node.get("name", ""),
            "thumbnail_url": "",
            "tags":          tags,
            "tags_by_dim":   group_tags_by_dimension(tags),
            "rights_valid":  _rights_are_valid(tags),
        })
        # Don't recurse into a tagged photo's children — they're internal
        return

    # Continue walking children
    for child in node.get("children", []) or []:
        _walk_for_tagged_photos(child, results)


def _is_tagged_photo_node(node: dict) -> bool:
    """Heuristic: True if this node is a tagged photo (image + 3+ recognized hidden tags as DIRECT children)."""
    node_type = node.get("type", "")
    if node_type not in {"FRAME", "COMPONENT", "INSTANCE"}:
        return False

    children = node.get("children", []) or []
    if not children:
        return False

    has_direct_image = False
    recognized_hidden_tags = 0
    tag_types = {"RECTANGLE", "FRAME", "INSTANCE", "COMPONENT", "ELLIPSE", "GROUP"}

    for child in children:
        if not isinstance(child, dict):
            continue
        # Image fill check (direct child)
        fills = child.get("fills") or []
        if isinstance(fills, list):
            for f in fills:
                if isinstance(f, dict) and f.get("type") == "IMAGE":
                    has_direct_image = True
                    break
        # Hidden tag check (direct child)
        if (child.get("visible") is False and child.get("type") in tag_types):
            name = (child.get("name") or "").strip()
            if name and tag_dimension(name) is not None:
                recognized_hidden_tags += 1

    return has_direct_image and recognized_hidden_tags >= 3


def _collect_direct_hidden_tag_names(node: dict) -> list[str]:
    """Return names of all hidden tag-eligible DIRECT children (one level only)."""
    names: list[str] = []
    tag_types = {"RECTANGLE", "FRAME", "INSTANCE", "COMPONENT", "ELLIPSE", "GROUP"}
    for child in node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        if child.get("visible") is False and child.get("type") in tag_types:
            name = (child.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _collect_hidden_tag_names(node: dict) -> list[str]:
    """Collect names of all hidden tag-eligible descendant nodes."""
    names: list[str] = []
    tag_types = {"RECTANGLE", "FRAME", "INSTANCE", "COMPONENT", "ELLIPSE", "GROUP"}

    def walk(n: dict) -> None:
        if not isinstance(n, dict):
            return
        if n.get("visible") is False and n.get("type") in tag_types:
            name = (n.get("name") or "").strip()
            if name:
                names.append(name)
        for c in n.get("children", []) or []:
            walk(c)

    for child in node.get("children", []) or []:
        walk(child)
    return names


def _has_image_descendant(node: dict) -> bool:
    """True if any descendant has an image fill."""
    def walk(n: dict) -> bool:
        if not isinstance(n, dict):
            return False
        fills = n.get("fills") or []
        if isinstance(fills, list):
            for f in fills:
                if isinstance(f, dict) and f.get("type") == "IMAGE":
                    return True
        for c in n.get("children", []) or []:
            if walk(c):
                return True
        return False

    for child in node.get("children", []) or []:
        if walk(child):
            return True
    return False


# ── MATCHING LOGIC ────────────────────────────────────────────────────────────

def _component_has_all(component: dict, required_tags: list[str]) -> bool:
    """True if the component has every tag in required_tags."""
    comp_tags = set(component.get("tags", []))
    return all(t in comp_tags for t in required_tags)


def _drop_lowest_priority(tags: list[str]) -> tuple[list[str], str]:
    """Remove tags belonging to the lowest-priority dimension present.

    Returns (remaining_tags, dimension_dropped).
    If no tags can be dropped (all are priority 1), returns (tags, "").
    """
    present_priorities = {}
    for t in tags:
        dim = tag_dimension(t)
        if dim and dim in DIMENSION_PRIORITY:
            p = DIMENSION_PRIORITY[dim]
            present_priorities.setdefault(p, set()).add(dim)

    if not present_priorities:
        return tags, ""

    max_priority = max(present_priorities.keys())
    if max_priority == 1:
        return tags, ""  # only style-priority tags remain; can't drop further

    dims_to_drop = present_priorities[max_priority]
    remaining = [t for t in tags if tag_dimension(t) not in dims_to_drop]
    dropped_dim_label = ",".join(sorted(dims_to_drop))
    return remaining, dropped_dim_label


def find_matching_photos(
    components: list[dict],
    required_tags: list[str],
    include_expired_rights: bool = False,
) -> tuple[list[dict], str, list[str]]:
    """Find components matching the required tags, with progressive fallback.

    Returns (candidates, match_strength, tags_actually_used)
      - candidates: list of component dicts that match
      - match_strength: one of
          "strict"         — all required tags matched
          "relaxed-{dim}"  — dropped tags from dimension group(s)
          "style-only"     — only style tag retained
          "none"           — nothing matched even with style-only
      - tags_actually_used: the tag subset that produced the match
    """
    # Filter by rights first
    pool = [c for c in components if include_expired_rights or c.get("rights_valid", True)]
    if not pool:
        return [], "none", []

    # Level 1: strict
    matches = [c for c in pool if _component_has_all(c, required_tags)]
    if matches:
        return matches, "strict", required_tags

    # Progressive fallback: drop lowest-priority dimensions one tier at a time
    current_tags = list(required_tags)
    dropped_log: list[str] = []

    while True:
        new_tags, dropped_dim = _drop_lowest_priority(current_tags)
        if not dropped_dim or new_tags == current_tags:
            break
        current_tags = new_tags
        dropped_log.append(dropped_dim)

        matches = [c for c in pool if _component_has_all(c, current_tags)]
        if matches:
            strength = "relaxed-" + ">".join(dropped_log)
            return matches, strength, current_tags

    # Fall through: try style tag only
    style_tags = [t for t in required_tags if tag_dimension(t) == "style"]
    if style_tags:
        matches = [c for c in pool if _component_has_all(c, style_tags)]
        if matches:
            return matches, "style-only", style_tags

    return [], "none", []


# ── HISTORY / SELECTION ───────────────────────────────────────────────────────

def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def recent_node_ids(history: dict, count: int = RECENT_SPRINT_COUNT) -> set[str]:
    sprints = history.get("sprints", [])
    recent = sprints[-count:] if sprints else []
    ids = set()
    for s in recent:
        ids.update(s.get("used_node_ids", []))
    return ids


def record_usage(sprint_id: str, node_ids: list[str]) -> None:
    history = load_history()
    sprints = history.get("sprints", [])
    existing = next((s for s in sprints if s.get("sprint_id") == sprint_id), None)
    if existing:
        existing["used_node_ids"] = list(set(existing.get("used_node_ids", []) + node_ids))
    else:
        sprints.append({
            "sprint_id":     sprint_id,
            "used_node_ids": node_ids,
            "recorded_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    history["sprints"] = sprints
    save_history(history)


def select_photo(
    candidates: list[dict],
    history: Optional[dict] = None,
    exclude_ids: Optional[list[str]] = None,
) -> Optional[dict]:
    """Pick one photo, preferring candidates not used in the last 3 sprints.

    `exclude_ids` lets the caller filter out specific node_ids (used by Split
    Screen to guarantee the second picked photo is different from the first).
    """
    if not candidates:
        return None
    history = history or load_history()
    recent = recent_node_ids(history)
    excluded = set(exclude_ids or [])
    eligible = [c for c in candidates if c.get("node_id") not in excluded]
    if not eligible:
        return None
    fresh = [c for c in eligible if c.get("node_id") not in recent]
    pool = fresh if fresh else eligible
    return random.choice(pool)


# ── HIGH-LEVEL API (Stage 03 entry point) ─────────────────────────────────────

def derive_required_tags(visual_style: str, order: dict) -> list[str]:
    """Given a visual_style and order context, derive the tag list to match against.

    This is the 'translator' between the order form and Brandon's tag vocabulary.
    Add heuristics here as the team learns which tags matter for which orders.
    """
    tags: list[str] = []

    # Style tag (always required)
    style_tag = VISUAL_STYLE_TO_TAG.get(visual_style)
    if style_tag:
        tags.append(style_tag)

    # Default: photo should include a laptop and at least one person
    # (These will drop out via progressive fallback if no matches)
    if style_tag in ("lifestyle_photo", "photo_with_text"):
        tags.append("laptop")
        # Prefer solo-person photos for these styles — but it's flexible;
        # the matcher will fall through if nothing has exactly one person.
        # We don't hard-require a specific gender here — let selection
        # pick randomly from the available matches to encourage diversity.

    # Targeting-driven mood hint
    targeting = (order.get("targeting") or "").lower()
    if "prospecting" in targeting:
        tags.append("confident")
    elif "retargeting" in targeting:
        tags.append("happy")

    return tags


def pick_photo_for_asset(
    visual_style: str,
    order: dict,
    sprint_id: str,
    components: Optional[list[dict]] = None,
    exclude_ids: Optional[list[str]] = None,
) -> dict:
    """Main entry point for Stage 03.

    Returns one of:
      {"is_photo_based": False, ...}                          — caller generates via Gemini
      {"is_photo_based": True, "figma_asset_id": "...", ...}  — caller uses library asset
      {"is_photo_based": True, "needs_human_selection": True} — no match, flag for human

    `exclude_ids` filters out specific node_ids — used by Split Screen to pick
    a second distinct photo after the first one is chosen.
    """
    if visual_style in NON_PHOTO_STYLES:
        return {"is_photo_based": False}

    if visual_style not in VISUAL_STYLE_TO_TAG:
        return {"is_photo_based": False, "reason": f"unknown style: {visual_style}"}

    if components is None:
        components = fetch_library_components()

    required = derive_required_tags(visual_style, order)
    candidates, strength, used_tags = find_matching_photos(components, required)

    if not candidates:
        return {
            "is_photo_based":        True,
            "figma_asset_id":        "",
            "figma_asset_url":       "",
            "figma_asset_name":      "",
            "match_strength":        "none",
            "required_tags":         required,
            "matched_tags_used":     [],
            "needs_human_selection": True,
        }

    chosen = select_photo(candidates, exclude_ids=exclude_ids)
    if not chosen:
        return {"is_photo_based": True, "needs_human_selection": True}

    return {
        "is_photo_based":        True,
        "figma_asset_id":        chosen["node_id"],
        "figma_asset_url":       chosen["thumbnail_url"],
        "figma_asset_name":      chosen["name"],
        "match_strength":        strength,
        "required_tags":         required,
        "matched_tags_used":     used_tags,
        "photo_tags":            chosen["tags"],
        "needs_human_selection": False,
    }


# ── MOCK DATA + CLI ───────────────────────────────────────────────────────────

MOCK_COMPONENTS = [
    {
        "node_id": "mock:1",
        "name": "Pink hair editor at desk",
        "thumbnail_url": "https://mock.figma.com/thumb/1.png",
        # woman_5 = the unique actor (Asian woman with pink hair from shoot 5)
        "tags": ["woman_5", "asian", "young_adult", "laptop", "home_office",
                 "dark", "typing", "lifestyle_photo", "rights_2027_12"],
    },
    {
        "node_id": "mock:2",
        "name": "Black woman at laptop with plants",
        "thumbnail_url": "https://mock.figma.com/thumb/2.png",
        # woman_6 = curly hair black woman from shoot 6
        "tags": ["woman_6", "black", "young_adult", "laptop", "home_office",
                 "warm", "typing", "lifestyle_photo", "rights_2027_12"],
    },
    {
        "node_id": "mock:3",
        "name": "Mature white woman headshot",
        "thumbnail_url": "https://mock.figma.com/thumb/3.png",
        # woman_8 = mature white woman in tech setting
        "tags": ["woman_8", "white", "mature", "corporate_office", "cool",
                 "confident", "testimonial", "rights_2027_12"],
    },
    {
        "node_id": "mock:4",
        "name": "Asian man in kitchen (expired rights)",
        "thumbnail_url": "https://mock.figma.com/thumb/4.png",
        # man_1 = mature Asian man from shoot 1 — rights have expired
        "tags": ["man_1", "asian", "mature", "phone", "kitchen",
                 "warm", "lifestyle_photo", "rights_2026_01"],
    },
    {
        "node_id": "mock:5",
        "name": "Hands on keyboard — for photo-with-text",
        "thumbnail_url": "https://mock.figma.com/thumb/5.png",
        "tags": ["hands_only", "laptop", "home_office", "neutral",
                 "typing", "photo_with_text", "rights_2027_12"],
    },
    {
        "node_id": "mock:6",
        "name": "Greenhouse team meeting",
        "thumbnail_url": "https://mock.figma.com/thumb/6.png",
        # multiple unique actors in one photo
        "tags": ["man_3", "man_4", "woman_7", "mixed", "young_adult",
                 "laptop", "greenhouse", "green", "meeting", "lifestyle_photo",
                 "rights_2027_12"],
    },
]


def _enrich_mock(comps: list[dict]) -> list[dict]:
    """Apply the same enrichment real fetch would, so mocks match real shape."""
    out = []
    for c in comps:
        tags = c["tags"]
        out.append({
            **c,
            "tags_by_dim":  group_tags_by_dimension(tags),
            "rights_valid": _rights_are_valid(tags),
        })
    return out


def _cmd_test():
    print("→ Running mock test (no Figma API call)\n")
    components = _enrich_mock(MOCK_COMPONENTS)

    test_cases = [
        ("Lifestyle Photo", {"targeting": "Prospecting"}),
        ("Testimonial", {"targeting": "Retargeting"}),
        ("Photo with Text", {"targeting": "Prospecting"}),
        ("Illustration", {"targeting": "Prospecting"}),
    ]

    for style, order in test_cases:
        print(f"  Visual style: {style}")
        result = pick_photo_for_asset(style, order, "test-sprint", components)
        summary = {k: v for k, v in result.items() if k != "photo_tags"}
        print(f"    → {json.dumps(summary, indent=6)}")
        if "photo_tags" in result:
            print(f"    photo tags: {', '.join(result['photo_tags'])}")
        print()

    print("  Expired-rights check: the `mock:4` entry should be filtered out")
    print("  (it has rights_2026_01 — expired by Feb 2026).\n")


def _cmd_list():
    print("→ Fetching library components from Figma...")
    components = fetch_library_components()
    print(f"  Found {len(components)} components\n")

    active = [c for c in components if c["rights_valid"]]
    expired = [c for c in components if not c["rights_valid"]]
    print(f"  Active (rights valid): {len(active)}")
    print(f"  Expired:               {len(expired)}\n")

    for c in components:
        rights_badge = "" if c["rights_valid"] else " [EXPIRED]"
        print(f"  {c['node_id']:<20} {c['name']}{rights_badge}")
        if c["tags"]:
            for dim, vals in c["tags_by_dim"].items():
                print(f"    {dim:<14} {', '.join(vals)}")
        else:
            print(f"    (no tags found — no hidden rectangles in this component)")
        print()


def _cmd_find(tag_csv: str):
    required = [t.strip() for t in tag_csv.split(",") if t.strip()]
    print(f"→ Finding photos matching: {required}\n")
    components = fetch_library_components()
    candidates, strength, used = find_matching_photos(components, required)
    print(f"  Match strength: {strength}")
    print(f"  Tags used for match: {used}")
    print(f"  Candidates: {len(candidates)}\n")
    for c in candidates[:10]:
        print(f"  {c['node_id']:<20} {c['name']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "--test":
        _cmd_test()
    elif cmd == "--list":
        _cmd_list()
    elif cmd == "--find":
        tags = sys.argv[2] if len(sys.argv) > 2 else "lifestyle_photo"
        _cmd_find(tags)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
