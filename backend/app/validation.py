import fitz  # PyMuPDF

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, MAX_OCR_PAGES, MAX_PAGES

MIN_TEXT_CHARS = 20  # below this across all pages => treated as scanned


class PdfValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_pdf(
    data: bytes,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_pages: int = MAX_PAGES,
    max_ocr_pages: int = MAX_OCR_PAGES,
) -> bool:
    """Validate the upload against the given tier limits. True if scanned (needs OCR)."""
    if len(data) > max_file_size_bytes:
        mb = max_file_size_bytes // (1024 * 1024)
        raise PdfValidationError(
            "TOO_LARGE", f"Max file size is {mb} MB.", 413
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
        if doc.page_count > max_pages:
            raise PdfValidationError(
                "TOO_MANY_PAGES", f"Max {max_pages} pages.", 400
            )
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        is_scanned = total_chars < MIN_TEXT_CHARS
        if is_scanned and doc.page_count > max_ocr_pages:
            raise PdfValidationError(
                "TOO_MANY_PAGES_OCR",
                f"Scanned PDFs are limited to {max_ocr_pages} pages.",
                400,
            )
        return is_scanned
    finally:
        doc.close()
