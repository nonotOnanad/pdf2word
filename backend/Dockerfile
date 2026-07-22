FROM python:3.11-slim

WORKDIR /srv

# libglib2.0-0: opencv-python-headless (via pdf2docx) links against glib on some builds
# tesseract-ocr + language packs, ghostscript: OCR pipeline (ocrmypdf)
# tesseract-ocr-osd: script/orientation detection for --rotate-pages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-osd \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-nld \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic.ini .
COPY migrations/ ./migrations/

ENV PORT=8000
EXPOSE 8000

# single worker: conversions are CPU/memory heavy; free tier has ~512MB.
# uvicorn's threadpool queues concurrent requests instead of forking workers.
# NOTE: --timeout-keep-alive is idle keep-alive only; long conversions are bounded by Render's platform request timeout, not uvicorn.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 130 --proxy-headers --forwarded-allow-ips="*"
