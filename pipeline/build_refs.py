#!/usr/bin/env python3
"""
build_refs.py
=============
Extracts text from all reference PDFs and saves as a single
refs_context.json file. Run this once, or whenever you update
a reference document.

Usage:
    python3 pipeline/build_refs.py

Output:
    configs/refs_context.json
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
REFS_DIR = BASE_DIR / "refs"
OUTPUT_PATH = BASE_DIR / "configs" / "refs_context.json"

# Map reference files to context keys
REF_FILES = {
    # Adrie's authoritative copy INSTRUCTIONS (field specs, voice, formatting,
    # legal guardrails, QA). Highest authority in the copy-gen prompt. Edit this
    # .txt + rerun build_refs.py to update ADAM's copy rules — no Python change.
    "copy_instructions": "meta_copy_instructions.txt",
    "brand_voice": "Claude * Upwork Brand Tone of Voice for Paid Ad copy .txt",
    "writing_style": "Upwork Writing Style Guide Audit - 2025 .txt",
    "compliance": "Revised Legal Guidance Content Guidelines .txt",
    "copy_playbook": "Claude Meta Ad_Copy_Mini_Playbook .txt",
    "approved_claims": "Copy of Marketing claims III .txt",
    "smb_copy_bank": "SMB Copy Bank_Phase 1_Final .txt",
    "keyword_research": "New : Trending Subcategory Keyword Research .txt",
    "copy_style_rules": "visual_style_copy_rules.txt",
    "image_style_rules": "visual_style_image_rules.txt",
    "prospecting_examples": "Prospecting ad copy examples Updated 2026 .txt",
    "retargeting_examples": "Retargeting Ad copy examples Updated 2026 .txt",
    "performance_data": "koth top 8 static styles with examples.txt",
}

def build():
    print("Building refs_context.json from reference documents...\n")

    context = {
        "_meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": str(REFS_DIR),
            "note": "Pre-built reference context. Rebuild with: python3 pipeline/build_refs.py"
        }
    }

    loaded = 0
    for key, filename in REF_FILES.items():
        fpath = REFS_DIR / filename
        if fpath.exists():
            with open(fpath) as f:
                content = f.read()
            context[key] = content
            loaded += 1
            print(f"  Loaded: {key} ({len(content):,} chars) <- {filename}")
        else:
            context[key] = ""
            print(f"  Missing: {filename}")

    # Save
    with open(OUTPUT_PATH, "w") as f:
        json.dump(context, f, indent=2)

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n  Saved: {OUTPUT_PATH}")
    print(f"  Size: {size_kb:.0f} KB")
    print(f"  Documents: {loaded}/{len(REF_FILES)}")
    print(f"\n  This file is read by the pipeline on every run.")
    print(f"  Re-run this script whenever you update a reference document.")


if __name__ == "__main__":
    build()
