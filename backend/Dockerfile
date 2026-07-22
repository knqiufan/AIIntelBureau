# Build context must be the repository root.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --upgrade pip && pip install . && pip install -r requirements.lock

WORKDIR /app
COPY backend/app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
