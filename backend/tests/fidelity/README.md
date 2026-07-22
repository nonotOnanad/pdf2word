# Fidelity harness (Phase 1)

Measures PDF→DOCX conversion **quality** so it can be tracked and defended,
rather than left to "fidelity may vary". Reference-free: no hand-made correct
answers needed.

## Files

| file | purpose |
|---|---|
| `scorer.py` | Scores one (pdf, docx) pair: text retention, tables, length, `nextColumn` bug, composite 0–100. |
| `run_fidelity.py` | Runs the **production** path over `corpus/`, writes `results/scorecard.md` + `.csv`. Establishes/defends the baseline. |
| `tune.py` | Runs named `pdf2docx` setting presets over `corpus/` and compares scores. For picking settings empirically. |
| `test_fidelity_gates.py` | Pytest regression gates (synthetic always-on; corpus opt-in via `FIDELITY_MIN_SCORE`). |
| `corpus/` | Real-world PDFs you provide (see its README). |

## Run (from `backend/`, venv active)

```
PYTHONPATH=. python -m tests.fidelity.run_fidelity   # baseline scorecard
PYTHONPATH=. python -m tests.fidelity.tune           # compare settings
PYTHONPATH=. python -m pytest tests/fidelity -q      # gates
```

## Workflow

1. Add real PDFs to `corpus/` (see `corpus/README.md`).
2. `run_fidelity` → read `results/scorecard.md`. That mean composite is your baseline.
3. `tune` → if a preset beats baseline on your corpus, wire those settings into
   `app/converter.py` (`cv.convert(docx_path, **settings)`).
4. Set `FIDELITY_MIN_SCORE` in CI just below your baseline so future changes
   can't silently regress quality.

## Metrics

- **text_retention** — fraction of source words that survived (the big one).
- **next_column** — must be `False`; a `True` is the LibreOffice/Google-Docs
  column-break bug regressing.
- **tables_found / table_cells** — reported for diagnosis (not scored, since
  reference-free scoring can't know the "right" count).
- **length_ratio** — sanity band; far from 1.0 means dropped or duplicated text.
