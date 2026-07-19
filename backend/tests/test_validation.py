import pytest

from app.validation import PdfValidationError, validate_pdf


def test_valid_pdf_passes(text_pdf):
    assert validate_pdf(text_pdf) is None


def test_not_a_pdf_rejected(not_a_pdf):
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(not_a_pdf)
    assert exc.value.code == "NOT_A_PDF"
    assert exc.value.status_code == 400


def test_too_large_rejected(text_pdf):
    padded = text_pdf + b"\0" * (20 * 1024 * 1024)
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(padded)
    assert exc.value.code == "TOO_LARGE"
    assert exc.value.status_code == 413


def test_encrypted_rejected(encrypted_pdf):
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(encrypted_pdf)
    assert exc.value.code == "ENCRYPTED"
    assert exc.value.status_code == 400


def test_too_many_pages_rejected(many_pages_pdf):
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(many_pages_pdf)
    assert exc.value.code == "TOO_MANY_PAGES"
    assert exc.value.status_code == 400


def test_scanned_rejected(scanned_pdf):
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(scanned_pdf)
    assert exc.value.code == "SCANNED"
    assert exc.value.status_code == 422


def test_corrupt_pdf_with_magic_bytes_rejected():
    corrupt = b"%PDF-1.7 garbage that is not a real pdf body"
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(corrupt)
    assert exc.value.code == "NOT_A_PDF"
