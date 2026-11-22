# syntax=docker/dockerfile:1

# Etapa de construcción: instala las dependencias de uv.lock en un entorno virtual.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Imagen final: solo el entorno virtual y el código, sin uv ni herramientas de construcción.
FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app ./app
# La imagen oficial de Python no trae el bytecode de la biblioteca estándar, y el usuario
# sin privilegios no puede escribirlo: sin esto, cada proceso nuevo (el del healthcheck,
# cada 10 s) recompila todo lo que importa.
RUN python -m compileall -q -j 0 /usr/local/lib/python3.12 /app/app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/health\", timeout=2)"]
CMD ["python", "-m", "app.main"]
