"""External integrations (Hightouch, Slack, etc.).

Each integration exposes a FastAPI router. Plug into app.py via:

    from integrations.hightouch import router as hightouch_router
    app.include_router(hightouch_router)
"""
