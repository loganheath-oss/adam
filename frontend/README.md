# ADAM frontend — design-system reference

This folder is a **reference implementation** of what the ADAM frontend *should*
look like: a design system on the stack we already run (FastAPI + server-rendered
HTML), no framework rewrite, no build step.

It is **isolated and safe**. It imports nothing from `main.py`, changes nothing in
the pipeline, and lives on the `frontend-design-system` branch. Deleting this
folder would have zero effect on the running tool. It exists to show the target
structure so we can decide with something concrete in front of us.

## The problem it solves

Today the UI is built by pasting HTML+CSS into each route in `main.py`:

| | Today (`main.py`) | This reference (`frontend/`) |
|---|---|---|
| Lines | **3,535** | tokens.css + components.py ≈ **360** |
| Nav definition | duplicated **×23** | defined **once** (`nav()`) |
| Inline `<style>` blocks | **12** | **0** — one `tokens.css` |
| Change the nav | edit 23 places | edit 1 place |
| Change a color / spacing | hunt through inline CSS | edit 1 token |

## How it's structured

Three files, a clean separation of concerns:

- **`tokens.css`** — *the look.* Colors, type, spacing, and every component's
  styling (`.nav`, `.btn`, `.card`, `.pill`, `.table` …). One source of truth for
  the whole UI. This is where "design system" actually lives.
- **`components.py`** — *the structure.* Small functions (`nav`, `layout`,
  `page_header`, `button`, `pill`, `feature_card`, `data_table`) that emit the
  markup. Pages compose these; they never write raw HTML.
- **`demo.py`** — *the proof.* Two real ADAM screens (dashboard + Sprint Runs)
  rebuilt from the components. Each page is ~15 lines instead of hundreds.

A page now reads like this:

```python
@app.get("/sprints")
def sprints():
    header = page_header("Sprint Runs", f"{n} sprints · click any row",
                         button("Refresh", "/sprints") + button("New Order", "/new", primary=True))
    rows = [[mono(u), sprint_id(sid), driver, platform, pill(status), actions] for ... ]
    return layout("Sprints", header + data_table(COLS, rows), active="/sprints")
```

## See it

- **Rendered preview:** open `preview.html` (self-contained, CSS inlined).
- **Run the live version:**
  ```bash
  # in the project venv (fastapi + uvicorn are already project deps)
  python3 frontend/demo.py     # -> http://127.0.0.1:8900
  ```
  Visit `/` and `/sprints`. Same look as the live tool, built from the system.

## How the real migration would go (Phase 1)

This is a slice, not the whole app. The full Phase-1 migration is incremental and
low-risk:

1. Lift the consolidated `tokens.css` in as the one stylesheet (retire the v9.5
   CSS that's currently injected/duplicated).
2. Port routes one at a time to `layout(...)` + components, behind the **same
   URLs**. Old and new pages coexist during the move — nothing breaks.
3. Once every route is ported, `main.py` is HTTP glue + calls to components; the
   HTML-in-strings is gone.
4. Document the system (this README + a page in the wiki) so the next owner —
   Upwork's team after August — can extend it.

Nothing here is throwaway: if we ever go to a component framework (Phase 3), these
tokens and component contracts port straight across.
