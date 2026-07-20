FROM python:3.11-slim

WORKDIR /srv

# opencv-python-headless (via pdf2docx) links against glib on some builds
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PORT=8000
EXPOSE 8000

# single worker: conversions are CPU/memory heavy; free tier has ~512MB.
# uvicorn's threadpool queues concurrent requests instead of forking workers.
# NOTE: --timeout-keep-alive is idle keep-alive only; long conversions are bounded by Render's platform request timeout, not uvicorn.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 130 --proxy-headers --forwarded-allow-ips="*"
