import re
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import ALLOWED_ORIGINS
from app.converter import ConversionError, convert_pdf_to_docx
from app.validation import PdfValidationError, validate_pdf

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="PDF to Word Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _safe_docx_name(filename: str | None) -> str:
    stem = Path(filename or "converted.pdf").stem
    stem = re.sub(r'[\x00-\x1f"\\;]', "", stem).strip() or "converted"
    return stem + ".docx"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/convert")
def convert(request: Request, file: UploadFile):
    data = file.file.read()
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
