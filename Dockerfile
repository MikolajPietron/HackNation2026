# The online demo: one container. FastAPI serves the API and the built frontend (app/static.py).
# No ZUS documents and no secrets go into the image (.dockerignore); keys come from the host's
# environment variables.

FROM node:24-slim AS web
WORKDIR /src
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/
RUN npm ci --workspace frontend
COPY frontend/ frontend/
RUN npm run build --workspace frontend

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYDANTIC_AI_NO_BANNER=1
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY --from=web /src/frontend/dist /app/frontend/dist
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
# One process: a chat turn holds the session's lock in memory (app/services/sessions.py).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
