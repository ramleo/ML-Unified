FROM python:3.11-slim
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser
RUN apt-get update && apt-get install -y --no-install-recommends freetds-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY routers/ routers/
COPY data/ data/
USER appuser
EXPOSE ${PORT:-7860}
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]