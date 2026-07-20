import fitz  # PyMuPDF
import pytest


def _pdf_with_text(pages: int = 3) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Hello page {i + 1}. This is real extractable text.")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def text_pdf() -> bytes:
    return _pdf_with_text(3)


@pytest.fixture
def table_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Quarterly Report")
    # simple 2x2 table grid drawn with lines
    for y in (100, 130, 160):
        page.draw_line((72, y), (400, y))
    for x in (72, 236, 400):
        page.draw_line((x, 100), (x, 160))
    page.insert_text((80, 120), "Item")
    page.insert_text((244, 120), "Amount")
    page.insert_text((80, 150), "Widgets")
    page.insert_text((244, 150), "42")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf() -> bytes:
    # Pages with no text layer at all (simulates a scan)
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(50, 50, 500, 700), color=(0, 0, 0), width=1)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf_many_pages() -> bytes:
    # 21 image-only pages: over the scanned-PDF OCR cap (20) but under MAX_PAGES
    doc = fitz.open()
    for _ in range(21):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(50, 50, 500, 700), color=(0, 0, 0), width=1)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_image_pdf() -> bytes:
    """A real 'scan': text rendered to a bitmap, embedded as a page image.

    No text layer at all — OCR is the only way to get the words back.
    """
    src = fitz.open()
    page = src.new_page()
    page.insert_text(
        (72, 120), "The quick brown fox jumps over the lazy dog.", fontsize=18
    )
    page.insert_text((72, 160), "OCR round trip test 12345.", fontsize=18)
    pix = page.get_pixmap(dpi=200)
    src.close()

    out = fitz.open()
    out_page = out.new_page(width=612, height=792)
    out_page.insert_image(out_page.rect, pixmap=pix)
    data = out.tobytes()
    out.close()
    return data


@pytest.fixture
def encrypted_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    doc.close()
    return data


@pytest.fixture
def many_pages_pdf() -> bytes:
    return _pdf_with_text(101)


@pytest.fixture
def not_a_pdf() -> bytes:
    return b"This is definitely not a PDF file, just plain text bytes."
