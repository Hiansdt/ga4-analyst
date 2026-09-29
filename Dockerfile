# One image serves both the API and the built frontend, so the deployed app is a single Cloud Run service.

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-install-project
COPY backend/src ./src
RUN uv sync --frozen
COPY --from=web /web/dist /app/web

ENV WEB_DIR=/app/web PATH="/app/backend/.venv/bin:$PATH"
USER nobody
# Cloud Run sets PORT; 8080 is its default.
CMD ["sh", "-c", "exec uvicorn analyst.bootstrap:build_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
