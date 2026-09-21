#!/usr/bin/env python3
"""Convert a wiki guide into markdown that survives Google Drive's importer.

Drive's markdown-to-Doc conversion mangles several things. Verified by
publishing and reading back, 2026-09-10 and 2026-09-15:

  - TABLES come out with an empty header row and literal ** in every cell.
  - <Angle-Brackets> are eaten as HTML tags and vanish entirely.
  - _Underscore_ pairs inside a code-ish token become emphasis (Template_X_Y
    rendered as Template_X*****Y).
  - Headings, bold, italic and lists convert correctly and are safe.

So: tables become bolded definition lists, angle brackets become square
brackets, and underscores get escaped. Everything else passes through.

Usage:  python3 scripts/wiki_to_gdoc.py docs/wiki/19-role-designer.md
Prints the Doc-safe markdown on stdout.
"""
import re
import sys


def table_to_list(block):
    """A markdown table -> a list Drive can render.

    Three shapes, handled differently, because getting this wrong produces
    confident nonsense rather than an obvious break:

      - EMPTY header row (| | |): every row is data. Term: definition.
      - Two real columns: term: definition, header dropped as redundant.
      - Three or more real columns: each row leads with its first cell, then
        one sub-bullet per remaining column, labelled with its header. Without
        the labels a three-column row reads as if column two defines column one.
    """
    rows = [r.strip() for r in block.strip().split("\n") if r.strip()]
    # A separator must contain a dash. Without that requirement an empty
    # header row "| | |" matches too, the first real row is mistaken for the
    # header, and one row silently vanishes from every such table.
    rows = [r for r in rows if not (re.match(r"^\|[\s:|-]+\|$", r) and "-" in r)]
    if not rows:
        return ""

    def cells(r):
        return [c.strip() for c in r.strip().strip("|").split("|")]

    head = cells(rows[0])
    header_is_real = any(h.strip().strip("*") for h in head)
    body = rows[1:] if header_is_real else rows
    out = []

    if header_is_real and len([h for h in head if h.strip()]) >= 3:
        labels = [h.strip().strip("*") for h in head]
        for r in body:
            c = cells(r)
            if not any(c):
                continue
            lead = c[0].strip().strip("*")
            out.append(f"- **{lead}**" if lead else "-")
            for i, val in enumerate(c[1:], start=1):
                if not val.strip():
                    continue
                lbl = labels[i] if i < len(labels) else ""
                out.append(f"    - {lbl + ': ' if lbl else ''}{val}")
        return "\n".join(out)

    for r in body:
        c = cells(r)
        if not any(c):
            continue
        lead = c[0].strip()
        rest = [x for x in c[1:] if x.strip()]
        lead_txt = lead if (lead.startswith("**") and lead.endswith("**")) else (f"**{lead}**" if lead else "")
        tail = ". ".join(rest)
        if lead_txt and tail:
            out.append(f"- {lead_txt}: {tail}")
        elif lead_txt:
            out.append(f"- {lead_txt}")
        elif tail:
            out.append(f"- {tail}")
    return "\n".join(out)


def convert(md):
    lines = md.split("\n")
    out, buf, in_fence = [], [], False
    for ln in lines:
        if ln.startswith("```"):
            if in_fence:
                # close: emit the fence body as an indented block, which Drive
                # renders as plain text rather than swallowing it.
                out.append("")
                out.extend("    " + b for b in buf)
                out.append("")
                buf = []
                in_fence = False
            else:
                if buf:
                    out.append(table_to_list("\n".join(buf)))
                    buf = []
                in_fence = True
            continue
        if in_fence:
            buf.append(ln)
            continue
        if ln.lstrip().startswith("|"):
            buf.append(ln)
            continue
        if buf:
            out.append(table_to_list("\n".join(buf)))
            buf = []
        out.append(ln)
    if buf:
        out.append(table_to_list("\n".join(buf)) if not in_fence else "\n".join("    " + b for b in buf))

    s = "\n".join(out)
    # Angle-bracket placeholders are eaten as HTML.
    s = re.sub(r"<([A-Za-z][A-Za-z0-9 _/-]*)>", r"[\1]", s)
    # Escape underscores inside identifier-ish tokens so they do not become emphasis.
    def esc(m):
        return m.group(0).replace("_", r"\_")
    s = re.sub(r"\b[A-Za-z][A-Za-z0-9-]*(?:_[A-Za-z0-9\[\]-]+)+", esc, s)
    # Collapse runs of blank lines.
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


if __name__ == "__main__":
    print(convert(open(sys.argv[1]).read()))
