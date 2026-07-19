import os
import tempfile

from pdf2docx import Converter


class ConversionError(Exception):
    pass


def convert_pdf_to_docx(pdf_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="pdf2word-") as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        docx_path = os.path.join(tmp, "output.docx")
        try:
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            cv = Converter(pdf_path)
            try:
                cv.convert(docx_path)
            finally:
                cv.close()
            with open(docx_path, "rb") as f:
                return f.read()
        except ConversionError:
            raise
        except Exception as exc:
            raise ConversionError(str(exc)) from exc
