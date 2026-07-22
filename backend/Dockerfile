# Build context must be the repository root so the local PowerMem source is used.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src
COPY docs/my/demo/ai_intel_bureau/backend/requirements.lock /tmp/requirements.lock
RUN pip install --upgrade pip && pip install ".[server,seekdb]" && pip install -r /tmp/requirements.lock

WORKDIR /app
COPY docs/my/demo/ai_intel_bureau/backend/app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
