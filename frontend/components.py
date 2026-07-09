"""
ADAM Design System — reusable UI components.

This is the pattern the frontend SHOULD follow. Every screen is composed from
these small functions instead of pasting raw HTML into each route. The look is
owned by tokens.css; structure is owned here. Neither is ever duplicated.

Contrast with today's main.py, where the nav markup + CSS is repeated across ~23
places, so a single change means 23 edits. Here the nav is defined ONCE (`nav()`),
and every page calls it.

No new dependencies, no build step — plain Python returning HTML strings, exactly
the stack we already run. This is Phase 1 of the design-system plan, made concrete.
"""
from __future__ import annotations

from html import escape
from typing import Iterable

# The nav is data now, not 23 copies of markup.
NAV_ITEMS = [
    ("New Order", "/new"),
    ("Sprints", "/sprints"),
    ("Wiki", "/wiki"),
    ("Ask ADAM", "/agent"),
    ("Sync Log", "/sync-log"),
    ("Learnings", "/learnings"),
]

# Status -> pill styling, in one place. Add a state once and every table uses it.
_PILL_TONE = {
    "complete": ("good", "Complete"),
    "awaiting_gate": ("wait", None),   # label falls back to the raw value
    "error": ("info", "Error"),
}


def nav(active: str = "") -> str:
    """The single definition of the top navigation."""
    parts = []
    for label, href in NAV_ITEMS:
        current = ' aria-current="page"' if href == active else ""
        parts.append(f'<a href="{escape(href)}"{current}>{escape(label)}</a>')
    links = "".join(parts)
    return (
        '<nav class="nav"><div class="nav__in">'
        '<a class="brand" href="/">'
        '<span class="brand__up">upwork</span>'
        '<span class="brand__bar"></span>'
        '<span class="brand__adam">ADAM</span></a>'
        f'<div class="nav__links">{links}</div>'
        '</div></nav>'
    )


def layout(title: str, body: str, active: str = "") -> str:
    """Full page shell. Every route returns layout(...) — one <head>, one nav,
    one stylesheet link. Change the chrome here, every page follows."""
    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(title)} · ADAM</title>"
        '<link rel="stylesheet" href="/tokens.css">'
        "</head><body>"
        f"{nav(active)}"
        f'<main class="page">{body}</main>'
        "</body></html>"
    )


def page_header(title: str, subtitle: str = "", actions: str = "") -> str:
    sub = f'<p class="page-header__sub">{escape(subtitle)}</p>' if subtitle else ""
    act = f'<div class="page-header__actions">{actions}</div>' if actions else ""
    return (
        '<header class="page-header"><div>'
        f'<h1 class="page-header__title">{escape(title)}</h1>{sub}</div>{act}</header>'
    )


def button(label: str, href: str = "#", primary: bool = False) -> str:
    cls = "btn btn--primary" if primary else "btn"
    return f'<a class="{cls}" href="{escape(href)}">{escape(label)}</a>'


def pill(status: str) -> str:
    """State encoded in color + shape, so it reads at a glance."""
    key = "awaiting_gate" if status.startswith("awaiting_gate") else status
    tone, label = _PILL_TONE.get(key, ("info", None))
    text = label or status.replace("_", " ")
    return f'<span class="pill pill--{tone}">{escape(text)}</span>'


def feature_card(kicker: str, title: str, desc: str, href: str = "#") -> str:
    return (
        f'<a class="card feature" href="{escape(href)}">'
        f'<span class="feature__k">{escape(kicker)}</span>'
        f'<div class="feature__title">{escape(title)}</div>'
        f'<p class="feature__desc">{escape(desc)}</p></a>'
    )


def data_table(columns: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    """rows contain pre-rendered cell HTML (pills, buttons, mono ids)."""
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        '<div class="tablewrap"><table class="table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )
