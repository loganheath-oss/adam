FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_TRANSPORT=http \
    PORT=8080

COPY mcp_server/requirements.txt /app/mcp_server/requirements.txt
RUN pip install -r /app/mcp_server/requirements.txt

COPY mcp_server /app/mcp_server
COPY pipeline /app/pipeline
COPY configs /app/configs
COPY refs /app/refs
# Seed data is baked into the image; on container start, the entrypoint copies
# anything missing from runs_seed/ into runs/ (which is volume-mounted at runtime).
COPY runs /app/runs_seed

EXPOSE 8080

CMD ["sh", "-c", "mkdir -p /app/runs && cp -rn /app/runs_seed/. /app/runs/ 2>/dev/null; exec python /app/mcp_server/server.py"]
