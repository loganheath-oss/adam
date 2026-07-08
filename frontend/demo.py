"""
ADAM Design System — runnable reference app.

Two real ADAM screens (dashboard + Sprint Runs) rebuilt entirely from the design
system. Same look as the live tool, but each page is ~15 lines composing shared
components instead of hundreds of lines of pasted HTML+CSS.

Run it:
    pip install fastapi uvicorn        # already in the project
    python3 frontend/demo.py           # -> http://127.0.0.1:8900

This is a standalone demo — it imports nothing from main.py and changes nothing
in the pipeline. It exists only to show the target frontend structure.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from components import (
    layout, page_header, button, pill, feature_card, data_table,
)

app = FastAPI(title="ADAM Design System — reference")
_TOKENS = (Path(__file__).parent / "tokens.css").read_text()

# Sample data (mirrors what the live Sprints page shows).
SPRINTS = [
    ("2026-07-16:02", "2026-07-meta-9f5e94ca3040", "verify fixes", "Meta", "complete"),
    ("2026-07-06:34", "2026-07-meta-2c347862ae8b", "ALL STYLES test", "Meta", "complete"),
    ("2026-07-03:08", "2026-07-meta-7b9af545b433", "Demo manifest",   "Meta", "complete"),
    ("2026-07-01:43", "2026-07-meta-88d27a3b6c47", "Adrie Etherington", "Meta", "awaiting_gate_2"),
    ("2026-07-21:01", "2026-07-meta-9a9962c5de2c", "Adrie Etherington", "Meta", "awaiting_gate_6"),
]


@app.get("/tokens.css")
def tokens() -> Response:
    return Response(_TOKENS, media_type="text/css")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    body = (
        '<p class="feature__k">Ad creative, on demand</p>'
        '<h1 class="hero">Start a new ad order,<br><em>or pick up a sprint.</em></h1>'
        '<div class="grid grid--2" style="margin-top:32px">'
        + feature_card("Create", "New Order",
                       "Brief, audience, styles, sizes — submit and ADAM builds it.", "/new")
        + feature_card("Track", "Sprint Runs",
                       "Every run, its status, and one-click into the gates.", "/sprints")
        + "</div>"
    )
    return layout("Home", body, active="/")


@app.get("/sprints", response_class=HTMLResponse)
def sprints() -> str:
    actions = button("Refresh", "/sprints") + button("New Order", "/new", primary=True)
    header = page_header("Sprint Runs",
                         f"{len(SPRINTS)} sprints · click any row to view details", actions)
    rows = []
    for updated, sid, driver, platform, status in SPRINTS:
        review = "" if status == "complete" else button("Review", f"/sprints/{sid}")
        rows.append([
            f'<span class="mono">{updated}</span>',
            f'<span class="id">{sid}</span>',
            driver, platform, pill(status),
            f'<div class="row-actions">{review}{button("Chat", "/agent")}</div>',
        ])
    table = data_table(
        ["Updated", "Sprint ID", "Driver", "Platform", "Status", ""], rows)
    return layout("Sprints", header + table, active="/sprints")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8900)
