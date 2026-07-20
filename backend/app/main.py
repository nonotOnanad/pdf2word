import re
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import ALLOWED_ORIGINS, MAX_FILE_SIZE_BYTES, RATE_LIMIT
from app.converter import ConversionError, convert_pdf_to_docx
from app.validation import PdfValidationError, validate_pdf

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="PDF to Word Converter")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"code": "RATE_LIMITED", "message": "Hourly limit reached — try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _safe_docx_name(filename: str | None) -> str:
    stem = Path(filename or "converted.pdf").stem
    stem = re.sub(r'[\x00-\x1f"\\;]', "", stem).strip() or "converted"
    return stem + ".docx"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/convert")
@limiter.limit(RATE_LIMIT)
def convert(request: Request, file: UploadFile):
    data = file.file.read(MAX_FILE_SIZE_BYTES + 1)
    try:
        validate_pdf(data)
        docx_bytes = convert_pdf_to_docx(data)
    except PdfValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
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
