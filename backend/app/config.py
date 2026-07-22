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

# --- Auth / accounts (Phase 4 Workstream A) ---
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5173")   # frontend origin
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")   # backend origin
MAGIC_LINK_TTL_MINUTES = int(os.environ.get("MAGIC_LINK_TTL_MINUTES", "15"))
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "30"))
SESSION_COOKIE = os.environ.get("SESSION_COOKIE", "pdf2word_session")
# Secure cookies require HTTPS; default on in production, off for local dev.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
AUTH_REQUEST_MAX_PER_HOUR = int(os.environ.get("AUTH_REQUEST_MAX_PER_HOUR", "5"))
# Cross-site cookie: frontend (Vercel) and API (Render) are different origins,
# so production needs SameSite=None (+Secure) for the session cookie to be sent.
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "lax").lower()

# --- Billing / Stripe (Phase 4 Workstream B) ---
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_ANNUAL = os.environ.get("STRIPE_PRICE_ANNUAL", "")
BILLING_SUCCESS_URL = os.environ.get("BILLING_SUCCESS_URL", APP_BASE_URL + "/billing/success")
BILLING_CANCEL_URL = os.environ.get("BILLING_CANCEL_URL", APP_BASE_URL + "/billing/cancel")

# PRO tier limits (Workstream C wires these into the convert path).
PRO_MAX_FILE_SIZE_MB = int(os.environ.get("PRO_MAX_FILE_SIZE_MB", "100"))
PRO_MAX_FILE_SIZE_BYTES = PRO_MAX_FILE_SIZE_MB * 1024 * 1024
PRO_MAX_PAGES = int(os.environ.get("PRO_MAX_PAGES", "500"))
PRO_MAX_OCR_PAGES = int(os.environ.get("PRO_MAX_OCR_PAGES", "200"))
PRO_MAX_BATCH_FILES = int(os.environ.get("PRO_MAX_BATCH_FILES", "25"))
