import re
from pathlib import Path

from fastapi import Depends, FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import ALLOWED_ORIGINS, MAX_FILE_SIZE_BYTES, RATE_LIMIT
from app.converter import ConversionError, convert_pdf_to_docx, text_pdf_to_docx
from app.ocr import OcrError, ocr_pdf
from app.validation import PdfValidationError, validate_pdf
from app.auth import get_current_user, user_for_token
from app.config import SESSION_COOKIE
from app.db import SessionLocal, get_db
from app.entitlements import active_subscription, resolve
from app.models import User
from app.auth_routes import router as auth_router
from app.billing_routes import router as billing_router
from app.db import Base, engine

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="PDF to Word Converter")
app.state.limiter = limiter

# Dev convenience: auto-create tables for SQLite. In production use Alembic
# migrations (see migrations/) with DATABASE_URL pointing at Postgres.
if str(engine.url).startswith("sqlite"):
    Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(billing_router)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"code": "RATE_LIMITED", "message": "Hourly limit reached — try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _is_pro_request(request: Request) -> bool:
    """True when the caller is a signed-in user with an active subscription.
    Such callers are exempt from the free hourly rate limit."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    db = SessionLocal()
    try:
        user = user_for_token(db, token)
        return user is not None and active_subscription(db, user) is not None
    finally:
        db.close()


def _safe_docx_name(filename: str | None) -> str:
    stem = Path(filename or "converted.pdf").stem
    stem = re.sub(r'[\x00-\x1f"\\;]', "", stem).strip() or "converted"
    return stem + ".docx"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/convert")
@limiter.limit(RATE_LIMIT, exempt_when=_is_pro_request)
def convert(request: Request, file: UploadFile,
            user: User | None = Depends(get_current_user),
            db=Depends(get_db)):
    limits = resolve(db, user)
    data = file.file.read(limits.max_file_size_bytes + 1)
    try:
        is_scanned = validate_pdf(
            data,
            max_file_size_bytes=limits.max_file_size_bytes,
            max_pages=limits.max_pages,
            max_ocr_pages=limits.max_ocr_pages,
        )
        if is_scanned:
            searchable_pdf = ocr_pdf(data)
            docx_bytes = text_pdf_to_docx(searchable_pdf)
        else:
            docx_bytes = convert_pdf_to_docx(data)
    except PdfValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
    except OcrError:
        return JSONResponse(
            status_code=500,
            content={"code": "OCR_FAILED", "message": "We couldn't read this scanned PDF."},
        )
    except ConversionError:
        return JSONResponse(
            status_code=500,
            content={"code": "CONVERSION_FAILED", "message": "We couldn't convert this PDF."},
        )

    out_name = _safe_docx_name(file.filename)
    return Response(
        content=docx_bytes,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
