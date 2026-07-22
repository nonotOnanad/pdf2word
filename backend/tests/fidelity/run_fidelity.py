"""Score the PRODUCTION conversion path over a corpus of real PDFs.

Converts every PDF in ./corpus using the same code the live app uses
(app.converter / app.ocr), scores each result, and writes a scorecard
(Markdown + CSV) to ./results. Use this to establish a quality baseline and
to prove a change didn't regress it.

Digital PDFs use convert_pdf_to_docx. Scanned PDFs use the OCR path, which
needs ocrmypdf + tesseract installed; if they're missing the file is marked
SKIPPED rather than failing the run.

Usage:
    python -m tests.fidelity.run_fidelity     # from backend/, venv active
"""
from __future__ import annotations

import csv
import glob
import os
from datetime import date

from app.converter import convert_pdf_to_docx, text_pdf_to_docx
from app.validation import validate_pdf, PdfValidationError
from tests.fidelity.scorer import score

HERE = os.path.dirname(__file__)
CORPUS = os.path.join(HERE, "corpus")
RESULTS = os.path.join(HERE, "results")


def _convert(data: bytes):
    """Return (docx_bytes, kind) or raise. Mirrors app/main.py routing."""
    is_scanned = validate_pdf(data)
    if is_scanned:
        from app.ocr import ocr_pdf  # imported lazily; may be unavailable
        searchable = ocr_pdf(data)
        return text_pdf_to_docx(searchable), "scanned"
    return convert_pdf_to_docx(data), "digital"


def main() -> None:
    pdfs = sorted(glob.glob(os.path.join(CORPUS, "*.pdf")))
    if not pdfs:
        print(f"No PDFs in {CORPUS}. See corpus/README.md for what to add.")
        return

    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for pdf_path in pdfs:
        name = os.path.basename(pdf_path)
        with open(pdf_path, "rb") as f:
            data = f.read()
        try:
            docx_bytes, kind = _convert(data)
            s = score(data, docx_bytes).as_dict()
            s.update(file=name, kind=kind, status="ok")
        except PdfValidationError as exc:
            s = {"file": name, "kind": "?", "status": f"rejected:{exc.code}"}
        except Exception as exc:  # noqa: BLE001
            s = {"file": name, "kind": "?", "status": f"error:{type(exc).__name__}"}
        rows.append(s)
        print(f"{name:<40} {s.get('status'):<18} "
              f"composite={s.get('composite', '-')}")

    # CSV
    fields = ["file", "kind", "status", "composite", "text_retention",
              "length_ratio", "tables_found", "table_cells", "next_column",
              "paragraphs", "valid_docx"]
    csv_path = os.path.join(RESULTS, "scorecard.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # Markdown
    scored = [r for r in rows if isinstance(r.get("composite"), (int, float))]
    avg = round(sum(r["composite"] for r in scored) / len(scored), 1) if scored else "-"
    md_path = os.path.join(RESULTS, "scorecard.md")
    with open(md_path, "w") as f:
        f.write(f"# Fidelity scorecard — {date.today().isoformat()}\n\n")
        f.write(f"Corpus: {len(rows)} files · scored: {len(scored)} · "
                f"mean composite: **{avg}**\n\n")
        f.write("| file | kind | status | composite | text_ret | tables | nextCol |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['file']} | {r.get('kind','?')} | {r['status']} | "
                    f"{r.get('composite','-')} | {r.get('text_retention','-')} | "
                    f"{r.get('tables_found','-')} | {r.get('next_column','-')} |\n")
    print(f"\nWrote {md_path}\nWrote {csv_path}\nMean composite: {avg}")


if __name__ == "__main__":
    main()
