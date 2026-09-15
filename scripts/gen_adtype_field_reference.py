#!/usr/bin/env python3
"""Generate the per-ad-type copy-field reference for whoever builds templates.

Elise asked for this on the 2026-09-10 call: "is there a document I should look
at that says, hey, this one gets a headline, this one gets primary, this one gets
CTA?" There wasn't one.

GENERATED, not written. The numbers live in configs/ad_type_style_guide.json and
are Adrie's to change; a hand-typed copy would silently rot the first time she
edits a cap. Re-run this after any style-guide change:

    python3 scripts/gen_adtype_field_reference.py

Writes docs/adtype-field-reference.md (and the web/ wiki copy is NOT written
here — this is a working reference for the design side, not a wiki page).
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUIDE = ROOT / "configs" / "ad_type_style_guide.json"
OUT = ROOT / "docs" / "adtype-field-reference.md"

# ADAM copy field -> the Figma text layer that carries it. Layer names come from
# docs/figma-naming-convention.md; multi-field styles use their own names, which
# are listed per style rather than guessed at here.
LAYER = {
    "creative_headline": "Copy_Headline",
    "creative_subhead": "Copy_Subhead",
    "cta": "Copy_CTA",
    "testimonial_quote": "Copy_Testimonial",
    "testimonial_author": "Copy_Author",
    "us_headline": "Copy_Headline-Left",
    "them_headline": "Copy_Headline-Right",
    "left_headline": "Copy_Headline-Left",
    "right_headline": "Copy_Headline-Right",
    "body": "Copy_Body",
}

FRIENDLY = {
    "creative_headline": "headline on the image",
    "creative_subhead": "subhead on the image",
    "cta": "CTA on the image",
    "testimonial_quote": "the quote",
    "testimonial_author": "attribution under the quote",
    "pie_labels": "quadrant labels (x4)",
    "pie_center": "centre callout",
    "us_bullets": "left bullets",
    "them_bullets": "right bullets",
    "left_bullets": "left bullets",
    "right_bullets": "right bullets",
    "single_bullets": "list items",
    "search_results": "each search result row",
    "chat_label": "chat name label",
    "chat_message": "chat message",
    "poll_question": "poll question",
    "poll_option_a": "poll option A",
    "poll_option_b": "poll option B",
    "profile_name": "profile name",
    "profile_title": "profile job title",
    "profile_left": "profile left field",
    "profile_right": "profile right field",
    "button_text": "button label",
    "single_headline": "headline",
    "body": "body copy",
}


def main():
    g = json.loads(GUIDE.read_text())
    entries = g["entries"]
    meta_feed = g.get("field_caps_meta_feed", {})
    reddit_feed = {k: v for k, v in (g.get("field_caps_reddit_feed") or {}).items()
                   if not k.startswith("_")}

    lines = [
        "# Which copy fields each ad type gets",
        "",
        "**Generated from `configs/ad_type_style_guide.json`. Do not hand-edit.** Run",
        "`python3 scripts/gen_adtype_field_reference.py` after any style-guide change.",
        "",
        "For whoever builds templates. Each entry lists the copy fields that ad type",
        "actually carries and the character budget for each, so a template can be built",
        "with the right number of text layers before a sprint ever runs.",
        "",
        "Text layers follow `Copy_<Role>`. Where a style has fields with no standard",
        "role name (pie quadrants, poll options, chat lines), the field is listed by its",
        "pipeline name and needs its own agreed layer name.",
        "",
        "## Feed copy, which is not on the image",
        "",
        "Shown around the ad, never printed on it.",
        "",
        f"- **Meta**: " + ", ".join(f"{k} ({v})" for k, v in meta_feed.items()),
        f"- **Reddit**: " + ", ".join(f"{k} ({v})" for k, v in reddit_feed.items())
        + ". One version only, no long/short pair.",
        "",
    ]

    for plat, prefix, label in (("Meta", None, "Meta ad types"),
                                ("Reddit", "reddit-", "Reddit ad types")):
        keys = [k for k in entries
                if (k.startswith(prefix) if prefix else not k.startswith("reddit-"))]
        lines += ["---", "", f"## {label} ({len(keys)})", ""]
        for k in keys:
            e = entries[k]
            name = e.get("name", k)
            caps = e.get("char_limits") or {}
            lines.append(f"### {name}")
            lines.append("")
            if e.get("layout"):
                lines.append(f"{e['layout']}")
                lines.append("")
            if not caps:
                lines.append("**No copy on the asset.**")
                lines.append("")
                continue
            hard = " Caps are enforced hard." if e.get("caps_are_physical") else ""
            lines.append(f"| Field | Max | Figma layer |{''}")
            lines.append("|---|---|---|")
            for f, cap in caps.items():
                friendly = FRIENDLY.get(f, f)
                layer = LAYER.get(f, "_needs an agreed layer name_")
                lines.append(f"| {friendly} (`{f}`) | {cap} | `{layer}` |")
            lines.append("")
            if hard:
                lines.append(hard.strip())
                lines.append("")

    OUT.write_text("\n".join(lines) + "\n")
    n_meta = len([k for k in entries if not k.startswith("reddit-")])
    n_red = len([k for k in entries if k.startswith("reddit-")])
    print(f"wrote {OUT.relative_to(ROOT)}  ({n_meta} Meta + {n_red} Reddit ad types)")


if __name__ == "__main__":
    main()
