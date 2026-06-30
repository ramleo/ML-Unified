FROM python:3.11-slim

WORKDIR /app

# libgomp1 is required by LightGBM and XGBoost for OpenMP parallelism
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY routers/ routers/
COPY shared/ shared/
COPY frontend/ frontend/
COPY --chown=appuser:appuser models/ models/
COPY --chown=appuser:appuser schemas/ schemas/
COPY --chown=appuser:appuser data/ data/

USER appuser
EXPOSE ${PORT:-8000}
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
