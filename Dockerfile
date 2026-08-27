FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt setup.py ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# NOTE: no ARG/ENV secrets baked into the image. All secrets (GEMINI_API_KEY,
# WHATSAPP_TOKEN, etc.) are injected at container RUN time via `-e` / your
# orchestrator's secret manager — never at build time, since build-time ENV
# values persist in the image layer history and are extractable.

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/log /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "deployment.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
