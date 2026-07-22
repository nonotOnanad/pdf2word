"""Compare pdf2docx conversion settings across the corpus.

pdf2docx's `Converter.convert(docx, **settings)` accepts ~30 tunables. The
production path (app.converter) uses the defaults. This harness runs each named
preset over every digital PDF in ./corpus and prints a fidelity comparison so
you can pick settings empirically instead of guessing.

Usage:
    python -m tests.fidelity.tune            # from backend/, venv active
"""
from __future__ import annotations

import io
import os
import glob
import tempfile

from pdf2docx import Converter

from app.converter import _fix_column_sections
from tests.fidelity.scorer import score

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")

# Named setting overrides layered on top of pdf2docx defaults. Add your own.
PRESETS: dict[str, dict] = {
    "baseline": {},
    # Turn on borderless ("stream") table extraction — helps tables that have
    # no drawn gridlines but costs some false positives on dense text.
    "tables_stream": {"extract_stream_table": True},
    # Treat list-like blocks as tables (default keeps them as lists).
    "lists_as_tables": {"list_not_table": False},
    # Looser paragraph splitting — fewer accidental paragraph breaks.
    "para_loose": {"new_paragraph_free_space_ratio": 0.95},
}


def convert_with_settings(pdf_bytes: bytes, settings: dict) -> bytes:
    with tempfile.TemporaryDirectory(prefix="fidelity-tune-") as tmp:
        pdf_path = os.path.join(tmp, "in.pdf")
        docx_path = os.path.join(tmp, "out.docx")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        cv = Converter(pdf_path)
        try:
            cv.convert(docx_path, **settings)
        finally:
            cv.close()
        with open(docx_path, "rb") as f:
            return _fix_column_sections(f.read())


def main() -> None:
    pdfs = sorted(glob.glob(os.path.join(CORPUS, "*.pdf")))
    if not pdfs:
        print(f"No PDFs in {CORPUS}. Drop real-world digital PDFs there first.")
        return

    for pdf_path in pdfs:
        name = os.path.basename(pdf_path)
        with open(pdf_path, "rb") as f:
            data = f.read()
        print(f"\n### {name}")
        print(f"{'preset':<16} {'composite':>9} {'text_ret':>9} {'tables':>7} {'cells':>6} {'nextCol':>8}")
        for preset, settings in PRESETS.items():
            try:
                out = convert_with_settings(data, settings)
                s = score(data, out)
                print(f"{preset:<16} {s.composite:>9} {s.text_retention:>9} "
                      f"{s.tables_found:>7} {s.table_cells:>6} {str(s.next_column):>8}")
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"{preset:<16}  ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
