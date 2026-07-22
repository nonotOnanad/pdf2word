# Fidelity corpus

Drop **real-world** PDFs here — the messy documents that actually expose
conversion problems. The synthetic PDFs in `tests/conftest.py` prove the code
runs; these prove it produces *good output*.

## What to add (aim for ~15–20)

- Simple single-column text (baseline)
- Multi-column layouts (newsletters, academic papers, brochures)
- Documents with **tables** — both gridlined and borderless
- Mixed text + images
- Dense/edge cases: footnotes, headers/footers, forms
- A few **scanned** PDFs (image-only) to exercise the OCR path

## Rules

- Use non-confidential / shareable files — this folder is committed to git.
- Keep them small (they run on every `tune`/`run_fidelity` pass).
- Name descriptively: `twocol-newsletter.pdf`, `invoice-table.pdf`,
  `scanned-contract.pdf`.

Scanned PDFs are scored via the OCR path, which needs `ocrmypdf` + `tesseract`
installed locally (as in the backend Dockerfile). Without them, scanned files
are marked SKIPPED rather than failing the run.
