import fitz  # PyMuPDF

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, MAX_PAGES

MIN_TEXT_CHARS = 20  # below this across all pages => treated as scanned


class PdfValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_pdf(data: bytes) -> None:
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise PdfValidationError(
            "TOO_LARGE", f"Max file size is {MAX_FILE_SIZE_MB} MB.", 413
        )
    if not data.startswith(b"%PDF"):
        raise PdfValidationError("NOT_A_PDF", "That file isn't a PDF.", 400)

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfValidationError("NOT_A_PDF", "That file isn't a PDF.", 400)

    try:
        if doc.needs_pass:
            raise PdfValidationError(
                "ENCRYPTED", "Password-protected PDFs aren't supported.", 400
            )
        if doc.page_count > MAX_PAGES:
            raise PdfValidationError(
                "TOO_MANY_PAGES", f"Max {MAX_PAGES} pages.", 400
            )
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        if total_chars < MIN_TEXT_CHARS:
            raise PdfValidationError(
                "SCANNED",
                "This looks like a scanned PDF — OCR isn't supported yet.",
                422,
            )
    finally:
        doc.close()
