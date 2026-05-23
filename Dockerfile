FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies before copying source — maximises layer cache hits
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"]
