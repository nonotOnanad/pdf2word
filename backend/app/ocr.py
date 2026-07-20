import os
import subprocess
import tempfile

from app.config import OCR_LANGUAGES, OCR_TIMEOUT_SECONDS


class OcrError(Exception):
    pass


def ocr_pdf(pdf_bytes: bytes) -> bytes:
    """Run OCR on a scanned PDF, returning a PDF with a text layer added.

    Invoked as a subprocess (not ocrmypdf's Python API) because ocrmypdf is not
    safe to call from web-server worker threads (it manages its own
    multiprocessing/signals).
    """
    with tempfile.TemporaryDirectory(prefix="pdf2word-ocr-") as tmp:
        in_path = os.path.join(tmp, "input.pdf")
        out_path = os.path.join(tmp, "output.pdf")
        with open(in_path, "wb") as f:
            f.write(pdf_bytes)

        cmd = [
            "ocrmypdf",
            "--language", OCR_LANGUAGES,
            "--output-type", "pdf",   # skip PDF/A conversion (faster, less memory)
            "--optimize", "0",        # no pngquant/jbig2 optimizers needed
            "--skip-text",            # never OCR pages that already have text
            "--rotate-pages",         # fix sideways scans (needs tesseract-ocr-osd)
            "--jobs", "1",            # keep memory flat on the 512MB tier
            "--quiet",
            in_path,
            out_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError("OCR timed out") from exc
        except FileNotFoundError as exc:
            raise OcrError("ocrmypdf is not installed") from exc

        # Exit code 0 = success. ocrmypdf uses nonzero codes for input/engine errors.
        if result.returncode != 0 or not os.path.exists(out_path):
            raise OcrError(
                f"ocrmypdf exited with {result.returncode}: "
                f"{result.stderr.decode(errors='replace')[:500]}"
            )

        with open(out_path, "rb") as f:
            return f.read()
