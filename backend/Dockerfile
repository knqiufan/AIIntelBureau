# Build context must be the repository root.
# renovate: datasource=docker depName=python versioning=docker
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --upgrade pip && pip install --require-hashes --requirement requirements.lock && pip check

WORKDIR /app
COPY backend/app ./app
RUN addgroup --system app && adduser --system --ingroup app --home /app app && mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
