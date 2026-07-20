import os

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_PAGES = 100
# Scanned PDFs go through OCR, which is ~5-10s/page on the free tier, so the
# cap is much lower than MAX_PAGES to stay inside the platform request timeout.
MAX_OCR_PAGES = int(os.environ.get("MAX_OCR_PAGES", "20"))
# Tesseract language stack. Multiple languages = broader coverage, slightly
# slower OCR. Packs must be installed in the image (see Dockerfile).
OCR_LANGUAGES = os.environ.get("OCR_LANGUAGES", "eng+spa+fra+deu+ita+por+nld")
OCR_TIMEOUT_SECONDS = int(os.environ.get("OCR_TIMEOUT_SECONDS", "240"))
RATE_LIMIT = os.environ.get("RATE_LIMIT", "10/hour")
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
