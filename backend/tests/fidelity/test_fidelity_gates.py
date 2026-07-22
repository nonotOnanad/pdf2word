"""Fidelity regression gates.

Two layers:
  1. Synthetic gates (always run) — use the shared conftest fixtures to assert
     the production path doesn't lose text, stays valid, and never emits the
     cross-app `nextColumn` break.
  2. Corpus gates (opt-in) — if real PDFs are in ./corpus, assert each scores
     above FIDELITY_MIN_SCORE (env, default 0 so CI stays green until you set a
     baseline). Raise it once you've run run_fidelity.py and know your floor.
"""
from __future__ import annotations

import glob
import os

import pytest

from app.converter import convert_pdf_to_docx
from tests.fidelity.scorer import score

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
MIN_SCORE = float(os.environ.get("FIDELITY_MIN_SCORE", "0"))


def test_text_pdf_retains_all_words(text_pdf):
    s = score(text_pdf, convert_pdf_to_docx(text_pdf))
    assert s.valid_docx
    assert not s.next_column
    assert s.text_retention >= 0.9, f"lost text: {s.as_dict()}"


def test_table_pdf_keeps_content(table_pdf):
    s = score(table_pdf, convert_pdf_to_docx(table_pdf))
    assert s.valid_docx
    assert s.text_retention >= 0.8, f"table content dropped: {s.as_dict()}"


def _corpus_pdfs():
    return sorted(glob.glob(os.path.join(CORPUS, "*.pdf")))


@pytest.mark.parametrize("pdf_path", _corpus_pdfs(),
                         ids=[os.path.basename(p) for p in _corpus_pdfs()])
def test_corpus_above_floor(pdf_path):
    with open(pdf_path, "rb") as f:
        data = f.read()
    s = score(data, convert_pdf_to_docx(data))
    assert s.valid_docx, f"{pdf_path} produced invalid docx"
    assert s.composite >= MIN_SCORE, (
        f"{os.path.basename(pdf_path)} scored {s.composite} < {MIN_SCORE}"
    )
