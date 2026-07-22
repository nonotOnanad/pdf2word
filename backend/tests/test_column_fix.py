import io
import zipfile

import fitz  # PyMuPDF
import pytest
from lxml import etree

from app.converter import NS, W, convert_pdf_to_docx


@pytest.fixture
def two_column_pdf() -> bytes:
    """PDF with a title plus two side-by-side text columns."""
    doc = fitz.open()
    page = doc.new_page()
    w = page.rect.width
    page.insert_textbox(
        fitz.Rect(50, 50, w - 50, 80), "Two Column Doc",
        fontsize=18, fontname="helv", align=fitz.TEXT_ALIGN_CENTER,
    )
    left = ("Left column text about operating expenses that remained flat "
            "quarter over quarter while headcount grew by eight percent.")
    right = ("Right column text about customer satisfaction scores improving "
             "to ninety four percent, the highest level recorded.")
    page.insert_textbox(fitz.Rect(50, 110, w / 2 - 15, 220), left,
                        fontsize=10, fontname="helv")
    page.insert_textbox(fitz.Rect(w / 2 + 15, 110, w - 50, 220), right,
                        fontsize=10, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def _document_xml(docx_bytes: bytes):
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        return etree.fromstring(z.read("word/document.xml"))


def test_no_next_column_section_breaks(two_column_pdf):
    """nextColumn breaks render as page breaks outside Word; must be rewritten."""
    result = convert_pdf_to_docx(two_column_pdf)
    root = _document_xml(result)
    types = [t.get(f"{{{W}}}val") for t in root.iter(f"{{{W}}}type")]
    assert "nextColumn" not in types


def test_column_break_inserted_for_merged_columns(two_column_pdf):
    result = convert_pdf_to_docx(two_column_pdf)
    root = _document_xml(result)
    # if any two-column section survives, an explicit column break must exist
    two_col = [c for c in root.iter(f"{{{W}}}cols") if c.get(f"{{{W}}}num") == "2"]
    if two_col:
        col_breaks = [
            b for b in root.iter(f"{{{W}}}br")
            if b.get(f"{{{W}}}type") == "column"
        ]
        assert col_breaks, "merged two-column section needs an explicit column break"


def test_single_column_pdf_unchanged(text_pdf):
    """Plain PDFs must pass through the post-processor untouched and valid."""
    import docx

    result = convert_pdf_to_docx(text_pdf)
    document = docx.Document(io.BytesIO(result))  # raises if corrupted
    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Hello page 1" in all_text


@pytest.fixture
def trailing_two_column_pdf() -> bytes:
    """Two-column layout whose LAST section lands in the body-level sectPr.

    Regression case: pdf2docx emits the final column section as a body-level
    <w:sectPr type="nextColumn">, which the original fix (paragraph-scoped)
    never rewrote — so the cross-app page-break bug survived on the last column.
    """
    doc = fitz.open()
    page = doc.new_page()
    w = page.rect.width
    page.insert_textbox(
        fitz.Rect(50, 50, w - 50, 80), "Two-Column Newsletter",
        fontsize=18, fontname="helv", align=fitz.TEXT_ALIGN_CENTER,
    )
    left = ("Operating expenses stayed flat quarter over quarter while headcount "
            "grew eight percent reflecting tighter vendor management and lower "
            "cloud spend across the platform teams this period overall.")
    right = ("Customer satisfaction climbed to ninety four percent the highest "
             "recorded driven by faster support response times and the new "
             "onboarding flow that shipped at the start of the quarter.")
    page.insert_textbox(fitz.Rect(50, 110, w / 2 - 15, 320), left,
                        fontsize=10, fontname="helv")
    page.insert_textbox(fitz.Rect(w / 2 + 15, 110, w - 50, 320), right,
                        fontsize=10, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def test_body_level_next_column_normalized(trailing_two_column_pdf):
    """No nextColumn may survive anywhere, including the final body sectPr."""
    result = convert_pdf_to_docx(trailing_two_column_pdf)
    root = _document_xml(result)
    types = [t.get(f"{{{W}}}val") for t in root.iter(f"{{{W}}}type")]
    assert "nextColumn" not in types, "trailing body-level nextColumn not rewritten"
    # a two-column layout that got merged must carry an explicit column break
    two_col = [c for c in root.iter(f"{{{W}}}cols") if c.get(f"{{{W}}}num") == "2"]
    if two_col:
        col_breaks = [b for b in root.iter(f"{{{W}}}br")
                      if b.get(f"{{{W}}}type") == "column"]
        assert col_breaks, "merged column section needs an explicit column break"
