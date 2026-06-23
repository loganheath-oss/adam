"""
Vercel serverless entry point.

Vercel's @vercel/python runtime imports this module and serves the exposed
ASGI `app`. All routes are rewritten to here via vercel.json. This deploy is a
UI/design preview: heavy pipeline SDKs are optional (main.py guards their
imports), so pages render even though pipeline execution is disabled here.
"""
import sys
from pathlib import Path

# main.py lives at the repo root, one level above this file.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402  (path setup must precede the import)
