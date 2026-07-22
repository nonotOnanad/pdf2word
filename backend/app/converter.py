import io
import os
import tempfile
import zipfile

import fitz  # PyMuPDF
from docx import Document
from lxml import etree
from pdf2docx import Converter

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


class ConversionError(Exception):
    pass


def _fix_column_sections(docx_bytes: bytes) -> bytes:
    """Rewrite pdf2docx's multi-column section breaks for cross-app fidelity.

    pdf2docx emits one section per column joined by a ``nextColumn`` section
    break. Word renders that correctly, but LibreOffice and Google Docs treat
    it as a page break, so everything after the first column is pushed onto a
    new page and the layout no longer matches the original PDF.

    Fix: merge each such pair into a single continuous multi-column section
    with an explicit column break, which renders identically everywhere.
    """
    zin = zipfile.ZipFile(io.BytesIO(docx_bytes))
    root = etree.fromstring(zin.read("word/document.xml"))
    body = root.find("w:body", NS)
    if body is None:
        return docx_bytes

    modified = False
    merged = True
    while merged:
        merged = False
        paras = list(body)
        breaks = []  # (paragraph index, sectPr, type value, cols signature)
        for i, el in enumerate(paras):
            if el.tag != f"{{{W}}}p":
                continue
            sect = el.find("w:pPr/w:sectPr", NS)
            if sect is None:
                continue
            type_el = sect.find("w:type", NS)
            type_val = type_el.get(f"{{{W}}}val") if type_el is not None else None
            cols = sect.find("w:cols", NS)
            sig = etree.tostring(cols) if cols is not None else b""
            breaks.append((i, sect, type_val, sig))

        for k in range(1, len(breaks)):
            _idx, sect, type_val, sig = breaks[k]
            prev_idx, prev_sect, _prev_type, prev_sig = breaks[k - 1]
            if type_val != "nextColumn" or sig != prev_sig:
                continue
            # This section starts in the next column of an identical layout:
            # merge it with the previous section.
            sect.find("w:type", NS).set(f"{{{W}}}val", "continuous")
            paras[prev_idx].find("w:pPr", NS).remove(prev_sect)
            # Explicit column break at the start of the merged column.
            for nxt in paras[prev_idx + 1:]:
                if nxt.tag != f"{{{W}}}p":
                    continue
                run = etree.Element(f"{{{W}}}r")
                br = etree.SubElement(run, f"{{{W}}}br")
                br.set(f"{{{W}}}type", "column")
                ppr = nxt.find("w:pPr", NS)
                nxt.insert(list(nxt).index(ppr) + 1 if ppr is not None else 0, run)
                break
            modified = True
            merged = True
            break

    # The document's final section is stored as a body-level <w:sectPr> (not
    # inside a paragraph), so the loop above never sees it. If it still carries
    # a nextColumn break, the cross-app page-break bug survives on the last
    # column. Normalize it the same way: continuous section + explicit column
    # break at the section start.
    body_sect = body.find("w:sectPr", NS)
    if body_sect is not None:
        type_el = body_sect.find("w:type", NS)
        type_val = type_el.get(f"{{{W}}}val") if type_el is not None else None
        if type_val == "nextColumn":
            body_cols = body_sect.find("w:cols", NS)
            body_sig = etree.tostring(body_cols) if body_cols is not None else b""
            paras = list(body)
            prev_idx = None
            prev_sig = None
            for i, el in enumerate(paras):
                if el.tag != f"{{{W}}}p":
                    continue
                s = el.find("w:pPr/w:sectPr", NS)
                if s is not None:
                    prev_idx = i
                    pc = s.find("w:cols", NS)
                    prev_sig = etree.tostring(pc) if pc is not None else b""
            # Only merge when the column layout matches (or there is no prior
            # section), so we never collapse genuinely different layouts.
            if prev_sig is None or prev_sig == body_sig:
                type_el.set(f"{{{W}}}val", "continuous")
                start = prev_idx + 1 if prev_idx is not None else 0
                for nxt in paras[start:]:
                    if nxt.tag != f"{{{W}}}p":
                        continue
                    run = etree.Element(f"{{{W}}}r")
                    br = etree.SubElement(run, f"{{{W}}}br")
                    br.set(f"{{{W}}}type", "column")
                    ppr = nxt.find("w:pPr", NS)
                    nxt.insert(list(nxt).index(ppr) + 1 if ppr is not None else 0, run)
                    break
                modified = True

    if not modified:
        return docx_bytes

    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = xml if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    return out.getvalue()


def text_pdf_to_docx(pdf_bytes: bytes) -> bytes:
    """Build a clean, editable .docx from a PDF's text layer.

    Used for OCR'd scanned PDFs: pdf2docx would embed the page scan as an image
    with invisible text on top, which is nearly impossible to edit. Extracting
    the recognized text into plain paragraphs gives a genuinely editable doc.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ConversionError(str(exc)) from exc

    try:
        out = Document()
        for page_index, page in enumerate(doc):
            if page_index > 0:
                out.add_page_break()
            blocks = page.get_text("blocks")
            # reading order: top-to-bottom, then left-to-right
            blocks.sort(key=lambda b: (round(b[1]), b[0]))
            for block in blocks:
                text = " ".join(block[4].split())
                if text:
                    out.add_paragraph(text)
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(str(exc)) from exc
    finally:
        doc.close()


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
                return _fix_column_sections(f.read())
        except ConversionError:
            raise
        except Exception as exc:
            raise ConversionError(str(exc)) from exc
