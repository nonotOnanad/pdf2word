# PDF-to-Word Web Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public free web app that converts digitally-created PDFs to editable .docx files using a self-hosted pdf2docx engine, with no file persistence.

**Architecture:** Monorepo with two deployables — a React + Vite + Tailwind SPA (Vercel) and a FastAPI backend in Docker (Render/Railway). Conversion is synchronous within the HTTP request; hard limits (20 MB, 100 pages, 10 conversions/hour/IP) keep requests bounded. No database, no storage; per-request temp dirs with guaranteed cleanup.

**Tech Stack:** Python 3.11, FastAPI, pdf2docx, PyMuPDF (fitz), slowapi, pytest, python-docx (test-only); React 18, Vite, Tailwind CSS, react-dropzone, Vitest + Testing Library.

## Global Constraints

- Max upload size: **20 MB** (`MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024`)
- Max page count: **100**
- Rate limit: **10 conversions/hour per IP** (configurable via `RATE_LIMIT` env var)
- Request timeout target: **120s**
- Digital PDFs only — encrypted and scanned (no-text-layer) PDFs are rejected
- No persistence: all temp files deleted in all code paths
- Error responses are JSON: `{"code": "<ERROR_CODE>", "message": "<user friendly>"}`
- Error codes and statuses (exact): `NOT_A_PDF` 400, `TOO_LARGE` 413, `TOO_MANY_PAGES` 400, `ENCRYPTED` 400, `SCANNED` 422, `RATE_LIMITED` 429, `CONVERSION_FAILED` 500
- CORS restricted to `ALLOWED_ORIGINS` env var (comma-separated; default `http://localhost:5173`)
- Frontend user-facing copy must include: "Your files are never stored."

## Repository Layout

```
pdf2word/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py        # limits + env settings
│   │   ├── validation.py    # PDF validation rules
│   │   ├── converter.py     # pdf2docx wrapper with temp-dir lifecycle
│   │   └── main.py          # FastAPI app: routes, CORS, rate limiting
│   ├── tests/
│   │   ├── conftest.py      # generated fixture PDFs
│   │   ├── test_validation.py
│   │   ├── test_converter.py
│   │   └── test_api.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api.js           # convertPdf(file) client
│   │   ├── App.jsx          # single-page UI with upload states
│   │   ├── main.jsx
│   │   └── index.css
│   ├── src/__tests__/App.test.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

### Task 1: Backend scaffold + health endpoint

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.main.app` (FastAPI instance) with `GET /api/health` → `200 {"status": "ok"}`; `app.config` constants `MAX_FILE_SIZE_BYTES: int`, `MAX_PAGES: int`, `RATE_LIMIT: str`, `ALLOWED_ORIGINS: list[str]`.

- [ ] **Step 1: Initialize repo and Python environment**

```bash
mkdir -p pdf2word/backend/app pdf2word/backend/tests pdf2word/frontend
cd pdf2word && git init
cd backend && python3 -m venv .venv && source .venv/bin/activate
```

Create `backend/requirements.txt`:

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
python-multipart==0.0.*
pdf2docx==0.5.*
PyMuPDF==1.24.*
slowapi==0.1.*
pytest==8.*
httpx==0.27.*
python-docx==1.1.*
```

Run: `pip install -r requirements.txt`
Expected: all packages install without error.

Create `backend/.gitignore` with:

```
.venv/
__pycache__/
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_api.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `backend/`): `python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/__init__.py`: empty file.

`backend/app/config.py`:

```python
import os

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_PAGES = 100
RATE_LIMIT = os.environ.get("RATE_LIMIT", "10/hour")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
```

`backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS

app = FastAPI(title="PDF to Word Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold with health endpoint"
```

---

### Task 2: PDF validation module

**Files:**
- Create: `backend/app/validation.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_validation.py`

**Interfaces:**
- Consumes: `app.config.MAX_FILE_SIZE_BYTES`, `app.config.MAX_PAGES`.
- Produces:
  - `class PdfValidationError(Exception)` with attributes `code: str`, `message: str`, `status_code: int`.
  - `def validate_pdf(data: bytes) -> None` — raises `PdfValidationError` on any rule violation, returns `None` when valid. Later tasks call this before conversion.
  - Test fixtures (function-scoped, each returns `bytes`): `text_pdf` (3 pages of real text), `table_pdf` (text + drawn table lines), `scanned_pdf` (pages with no text layer), `encrypted_pdf`, `many_pages_pdf` (101 pages), `not_a_pdf` (plain bytes).

- [ ] **Step 1: Write fixture generators**

`backend/tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_validation.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.validation'`

- [ ] **Step 4: Write the implementation**

`backend/app/validation.py`:

```python
import fitz  # PyMuPDF

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, MAX_PAGES

MIN_TEXT_CHARS = 20  # below this across all pages => treated as scanned


class PdfValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_pdf(data: bytes) -> None:
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise PdfValidationError(
            "TOO_LARGE", f"Max file size is {MAX_FILE_SIZE_MB} MB.", 413
        )
    if not data.startswith(b"%PDF"):
        raise PdfValidationError("NOT_A_PDF", "That file isn't a PDF.", 400)

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfValidationError("NOT_A_PDF", "That file isn't a PDF.", 400)

    try:
        if doc.needs_pass:
            raise PdfValidationError(
                "ENCRYPTED", "Password-protected PDFs aren't supported.", 400
            )
        if doc.page_count > MAX_PAGES:
            raise PdfValidationError(
                "TOO_MANY_PAGES", f"Max {MAX_PAGES} pages.", 400
            )
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        if total_chars < MIN_TEXT_CHARS:
            raise PdfValidationError(
                "SCANNED",
                "This looks like a scanned PDF — OCR isn't supported yet.",
                422,
            )
    finally:
        doc.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/validation.py backend/tests/
git commit -m "feat: PDF validation with size/pages/encryption/scanned rules"
```

---

### Task 3: Conversion module

**Files:**
- Create: `backend/app/converter.py`
- Test: `backend/tests/test_converter.py`

**Interfaces:**
- Consumes: fixtures `text_pdf`, `table_pdf` from `conftest.py`.
- Produces: `def convert_pdf_to_docx(pdf_bytes: bytes) -> bytes` — returns .docx bytes; raises `ConversionError(Exception)` on failure. Uses a `tempfile.TemporaryDirectory` so cleanup is guaranteed in all paths.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_converter.py`:

```python
import io
import os
import tempfile

import docx  # python-docx, test-only dependency

from app.converter import convert_pdf_to_docx


def test_converts_text_pdf_to_valid_docx(text_pdf):
    result = convert_pdf_to_docx(text_pdf)
    document = docx.Document(io.BytesIO(result))  # raises if not a valid docx
    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Hello page 1" in all_text


def test_converts_table_pdf(table_pdf):
    result = convert_pdf_to_docx(table_pdf)
    document = docx.Document(io.BytesIO(result))
    assert len(result) > 0
    # content lands either in paragraphs or a detected table
    all_text = "\n".join(p.text for p in document.paragraphs)
    table_text = "".join(
        cell.text for t in document.tables for row in t.rows for cell in row.cells
    )
    assert "Widgets" in (all_text + table_text)


def test_no_temp_files_left_behind(text_pdf):
    tmp = tempfile.gettempdir()
    before = set(os.listdir(tmp))
    convert_pdf_to_docx(text_pdf)
    after = set(os.listdir(tmp))
    leftovers = [f for f in after - before if "pdf2word" in f]
    assert leftovers == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_converter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.converter'`

- [ ] **Step 3: Write the implementation**

`backend/app/converter.py`:

```python
import os
import tempfile

from pdf2docx import Converter


class ConversionError(Exception):
    pass


def convert_pdf_to_docx(pdf_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="pdf2word-") as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        docx_path = os.path.join(tmp, "output.docx")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        cv = Converter(pdf_path)
        try:
            cv.convert(docx_path)
        except Exception as exc:
            raise ConversionError(str(exc)) from exc
        finally:
            cv.close()

        with open(docx_path, "rb") as f:
            return f.read()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_converter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/converter.py backend/tests/test_converter.py
git commit -m "feat: pdf2docx conversion wrapper with guaranteed temp cleanup"
```

---

### Task 4: /api/convert endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py` (append)

**Interfaces:**
- Consumes: `validate_pdf`, `PdfValidationError` (Task 2); `convert_pdf_to_docx`, `ConversionError` (Task 3).
- Produces: `POST /api/convert` — multipart field `file`; success: 200 with `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document` and `Content-Disposition: attachment; filename="<original-stem>.docx"`; errors: JSON `{"code", "message"}` with the status codes from Global Constraints.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_api.py`:

```python
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(data: bytes, filename: str = "sample.pdf"):
    return client.post(
        "/api/convert", files={"file": (filename, data, "application/pdf")}
    )


def test_convert_success(text_pdf):
    resp = _upload(text_pdf, "report.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == DOCX_MIME
    assert 'filename="report.docx"' in resp.headers["content-disposition"]
    assert len(resp.content) > 0


def test_convert_rejects_non_pdf(not_a_pdf):
    resp = _upload(not_a_pdf, "fake.pdf")
    assert resp.status_code == 400
    assert resp.json()["code"] == "NOT_A_PDF"


def test_convert_rejects_encrypted(encrypted_pdf):
    resp = _upload(encrypted_pdf)
    assert resp.status_code == 400
    assert resp.json()["code"] == "ENCRYPTED"


def test_convert_rejects_scanned(scanned_pdf):
    resp = _upload(scanned_pdf)
    assert resp.status_code == 422
    assert resp.json()["code"] == "SCANNED"


def test_convert_rejects_too_many_pages(many_pages_pdf):
    resp = _upload(many_pages_pdf)
    assert resp.status_code == 400
    assert resp.json()["code"] == "TOO_MANY_PAGES"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -v`
Expected: `test_health` PASS; the five new tests FAIL with 404 (`Not Found`) — endpoint doesn't exist yet.

- [ ] **Step 3: Write the implementation**

Replace `backend/app/main.py` with:

```python
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import ALLOWED_ORIGINS
from app.converter import ConversionError, convert_pdf_to_docx
from app.validation import PdfValidationError, validate_pdf

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="PDF to Word Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/convert")
def convert(request: Request, file: UploadFile):
    data = file.file.read()
    try:
        validate_pdf(data)
        docx_bytes = convert_pdf_to_docx(data)
    except PdfValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
    except ConversionError:
        return JSONResponse(
            status_code=500,
            content={"code": "CONVERSION_FAILED", "message": "We couldn't convert this PDF."},
        )

    out_name = Path(file.filename or "converted.pdf").stem + ".docx"
    return Response(
        content=docx_bytes,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
```

Note: the endpoint is a sync `def`, so FastAPI runs it in its threadpool — the event loop stays responsive during conversion.

- [ ] **Step 4: Run all backend tests**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: /api/convert endpoint with validation and error mapping"
```

---

### Task 5: Rate limiting

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py` (append)

**Interfaces:**
- Consumes: `app.config.RATE_LIMIT` (default `"10/hour"`, env-overridable).
- Produces: `/api/convert` returns 429 JSON `{"code": "RATE_LIMITED", "message": "Hourly limit reached — try again later."}` once the per-IP limit is exceeded. `/api/health` is not rate-limited.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_api.py`:

```python
def test_rate_limit(monkeypatch, text_pdf):
    # Rebuild app with a tiny limit so the test is fast
    monkeypatch.setenv("RATE_LIMIT", "2/hour")
    import importlib

    from app import config, main
    importlib.reload(config)
    importlib.reload(main)
    from fastapi.testclient import TestClient as TC

    local_client = TC(main.app)
    for _ in range(2):
        ok = local_client.post(
            "/api/convert", files={"file": ("a.pdf", text_pdf, "application/pdf")}
        )
        assert ok.status_code == 200
    limited = local_client.post(
        "/api/convert", files={"file": ("a.pdf", text_pdf, "application/pdf")}
    )
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"

    # restore modules for other tests
    monkeypatch.delenv("RATE_LIMIT")
    importlib.reload(config)
    importlib.reload(main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_rate_limit -v`
Expected: FAIL — third request returns 200, not 429.

- [ ] **Step 3: Add slowapi to the app**

In `backend/app/main.py`, add imports and limiter wiring (final file shown; this replaces the previous version):

```python
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import ALLOWED_ORIGINS, RATE_LIMIT
from app.converter import ConversionError, convert_pdf_to_docx
from app.validation import PdfValidationError, validate_pdf

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="PDF to Word Converter")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"code": "RATE_LIMITED", "message": "Hourly limit reached — try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/convert")
@limiter.limit(RATE_LIMIT)
def convert(request: Request, file: UploadFile):
    data = file.file.read()
    try:
        validate_pdf(data)
        docx_bytes = convert_pdf_to_docx(data)
    except PdfValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
    except ConversionError:
        return JSONResponse(
            status_code=500,
            content={"code": "CONVERSION_FAILED", "message": "We couldn't convert this PDF."},
        )

    out_name = Path(file.filename or "converted.pdf").stem + ".docx"
    return Response(
        content=docx_bytes,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
```

- [ ] **Step 4: Run all backend tests**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests, including `test_rate_limit`)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: per-IP rate limiting on /api/convert"
```

---

### Task 6: Dockerfile + deployment config

**Files:**
- Create: `backend/Dockerfile`
- Create: `render.yaml`

**Interfaces:**
- Consumes: the working FastAPI app from Tasks 1–5.
- Produces: a container listening on `$PORT` (Render convention, default 8000) running `uvicorn app.main:app`. Render blueprint wiring health check to `/api/health` and env vars `ALLOWED_ORIGINS`, `RATE_LIMIT`.

- [ ] **Step 1: Write the Dockerfile**

`backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PORT=8000
EXPOSE 8000

# single worker: conversions are CPU/memory heavy; free tier has ~512MB.
# uvicorn's threadpool queues concurrent requests instead of forking workers.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 130
```

- [ ] **Step 2: Build and smoke-test the container**

Run (from `backend/`):

```bash
docker build -t pdf2word-api .
docker run -d -p 8000:8000 --name pdf2word-test pdf2word-api
sleep 3
curl -s http://localhost:8000/api/health
```

Expected: `{"status":"ok"}`

Cleanup: `docker rm -f pdf2word-test`

- [ ] **Step 3: Write the Render blueprint**

`render.yaml` (repo root):

```yaml
services:
  - type: web
    name: pdf2word-api
    runtime: docker
    rootDir: backend
    plan: free
    healthCheckPath: /api/health
    envVars:
      - key: ALLOWED_ORIGINS
        value: http://localhost:5173   # replace with prod frontend URL after Vercel deploy
      - key: RATE_LIMIT
        value: 10/hour
```

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile render.yaml
git commit -m "feat: Docker image and Render deployment blueprint"
```

---

### Task 7: Frontend scaffold + API client

**Files:**
- Create: `frontend/` via Vite scaffold (package.json, index.html, vite.config.js, src/main.jsx, src/index.css)
- Create: `frontend/src/api.js`
- Test: `frontend/src/__tests__/api.test.js`

**Interfaces:**
- Consumes: backend `POST /api/convert` contract (Task 4/5): success → docx blob; error → JSON `{code, message}`.
- Produces: `async function convertPdf(file: File): Promise<{ blob: Blob, filename: string }>` — throws `ApiError` with properties `code: string`, `message: string` on failure. `class ApiError extends Error`. Base URL from `import.meta.env.VITE_API_URL` (default `http://localhost:8000`).

- [ ] **Step 1: Scaffold Vite app with Tailwind and test tooling**

Run (from repo root):

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-dropzone
npm install -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Replace `frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.js',
  },
})
```

Replace `frontend/src/index.css` with:

```css
@import "tailwindcss";
```

Create `frontend/src/test-setup.js`:

```js
import '@testing-library/jest-dom'
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

Run: `npm run dev` briefly to confirm the scaffold serves, then stop it.

- [ ] **Step 2: Write the failing API client test**

`frontend/src/__tests__/api.test.js`:

```js
import { describe, it, expect, vi, afterEach } from 'vitest'
import { convertPdf, ApiError } from '../api'

afterEach(() => vi.restoreAllMocks())

const fakeFile = new File([new Uint8Array([1, 2, 3])], 'report.pdf', {
  type: 'application/pdf',
})

describe('convertPdf', () => {
  it('returns blob and filename on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new Blob(['docx-bytes']),
      {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="report.docx"' },
      },
    )))
    const { blob, filename } = await convertPdf(fakeFile)
    expect(filename).toBe('report.docx')
    expect(blob.size).toBeGreaterThan(0)
  })

  it('throws ApiError with code on API error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ code: 'SCANNED', message: 'This looks like a scanned PDF — OCR isn\'t supported yet.' }),
      { status: 422, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(convertPdf(fakeFile)).rejects.toMatchObject({ code: 'SCANNED' })
  })

  it('throws ApiError with NETWORK code when fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    await expect(convertPdf(fakeFile)).rejects.toBeInstanceOf(ApiError)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `../api` module not found.

- [ ] **Step 4: Write the implementation**

`frontend/src/api.js`:

```js
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

export async function convertPdf(file) {
  const form = new FormData()
  form.append('file', file)

  let resp
  try {
    resp = await fetch(`${API_URL}/api/convert`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('NETWORK', 'Could not reach the server. Try again in a moment.')
  }

  if (!resp.ok) {
    let code = 'UNKNOWN'
    let message = 'Something went wrong. Please try again.'
    try {
      const body = await resp.json()
      code = body.code || code
      message = body.message || message
    } catch { /* non-JSON error body */ }
    throw new ApiError(code, message)
  }

  const disposition = resp.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="(.+?)"/)
  const filename = match ? match[1] : 'converted.docx'
  const blob = await resp.blob()
  return { blob, filename }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold and typed API client"
```

---

### Task 8: Upload UI with conversion states

**Files:**
- Create: `frontend/src/App.jsx` (replace scaffold version)
- Modify: `frontend/src/main.jsx` (ensure it renders `App` and imports `index.css`)
- Test: `frontend/src/__tests__/App.test.jsx`

**Interfaces:**
- Consumes: `convertPdf`, `ApiError` from `src/api.js` (Task 7).
- Produces: single-page UI with states `idle | converting | done | error`. Client-side pre-checks mirror server rules: extension `.pdf`, size ≤ 20 MB (constant `MAX_SIZE_BYTES = 20 * 1024 * 1024`). Page copy includes "Your files are never stored."

- [ ] **Step 1: Write the failing component tests**

`frontend/src/__tests__/App.test.jsx`:

```jsx
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

vi.mock('../api', () => ({
  convertPdf: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(code, message) { super(message); this.code = code }
  },
}))
import { convertPdf } from '../api'

afterEach(() => vi.clearAllMocks())

function makePdf(name = 'doc.pdf', sizeBytes = 1000) {
  return new File([new Uint8Array(sizeBytes)], name, { type: 'application/pdf' })
}

describe('App', () => {
  it('shows privacy copy', () => {
    render(<App />)
    expect(screen.getByText(/your files are never stored/i)).toBeInTheDocument()
  })

  it('converts a file and shows download button', async () => {
    convertPdf.mockResolvedValue({ blob: new Blob(['x']), filename: 'doc.docx' })
    render(<App />)
    const input = screen.getByTestId('file-input')
    await userEvent.upload(input, makePdf())
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /download/i })).toBeInTheDocument(),
    )
  })

  it('rejects oversized file client-side', async () => {
    render(<App />)
    const input = screen.getByTestId('file-input')
    await userEvent.upload(input, makePdf('big.pdf', 21 * 1024 * 1024))
    expect(await screen.findByText(/max file size is 20 mb/i)).toBeInTheDocument()
    expect(convertPdf).not.toHaveBeenCalled()
  })

  it('shows API error message', async () => {
    const { ApiError } = await import('../api')
    convertPdf.mockRejectedValue(new ApiError('SCANNED', "This looks like a scanned PDF — OCR isn't supported yet."))
    render(<App />)
    await userEvent.upload(screen.getByTestId('file-input'), makePdf())
    expect(await screen.findByText(/scanned pdf/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: App tests FAIL (scaffold `App.jsx` has none of these elements).

- [ ] **Step 3: Write the implementation**

`frontend/src/App.jsx`:

```jsx
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { convertPdf } from './api'

const MAX_SIZE_BYTES = 20 * 1024 * 1024

export default function App() {
  const [status, setStatus] = useState('idle') // idle | converting | done | error
  const [error, setError] = useState('')
  const [download, setDownload] = useState(null) // { url, filename }

  const reset = () => {
    if (download) URL.revokeObjectURL(download.url)
    setDownload(null)
    setError('')
    setStatus('idle')
  }

  const handleFile = useCallback(async (file) => {
    reset()
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError("That file isn't a PDF.")
      setStatus('error')
      return
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError('Max file size is 20 MB.')
      setStatus('error')
      return
    }
    setStatus('converting')
    try {
      const { blob, filename } = await convertPdf(file)
      setDownload({ url: URL.createObjectURL(blob), filename })
      setStatus('done')
    } catch (e) {
      setError(e.message || 'Something went wrong.')
      setStatus('error')
    }
  }, [download])

  const onDrop = useCallback((accepted) => handleFile(accepted[0]), [handleFile])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
  })

  return (
    <main className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <h1 className="text-3xl font-bold text-slate-800 mb-2">PDF to Word</h1>
      <p className="text-slate-500 mb-8">
        Convert PDFs to editable .docx — free. Your files are never stored.
      </p>

      <div
        {...getRootProps()}
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white'}`}
      >
        <input {...getInputProps()} data-testid="file-input" />
        {status === 'converting' ? (
          <p className="text-slate-600 animate-pulse">Converting…</p>
        ) : (
          <p className="text-slate-600">
            Drag a PDF here, or click to choose a file (max 20 MB, 100 pages)
          </p>
        )}
      </div>

      {status === 'done' && download && (
        <a
          href={download.url}
          download={download.filename}
          className="mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
        >
          Download {download.filename}
        </a>
      )}

      {status === 'error' && (
        <p className="mt-6 text-red-600" role="alert">{error}</p>
      )}
    </main>
  )
}
```

Ensure `frontend/src/main.jsx` is:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS (all frontend tests)

- [ ] **Step 5: Manual smoke test against local backend**

```bash
# terminal 1, from backend/:
uvicorn app.main:app --port 8000
# terminal 2, from frontend/:
npm run dev
```

Open http://localhost:5173, drop a real PDF, confirm the .docx downloads and opens in Word/LibreOffice.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: upload UI with converting/done/error states"
```

---

### Task 9: README + deploy + manual E2E checklist

**Files:**
- Create: `README.md`
- Create: `frontend/.env.production` (after backend deploy)

**Interfaces:**
- Consumes: everything above.
- Produces: deployed app; README covering local dev, tests, and deploy steps.

- [ ] **Step 1: Write README.md**

```markdown
# PDF to Word Converter

Free web tool that converts digital PDFs to editable .docx. Files are never stored.

## Stack
- `frontend/` — React + Vite + Tailwind (Vercel)
- `backend/` — FastAPI + pdf2docx (Docker on Render)

## Local development
    # backend
    cd backend && python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --port 8000

    # frontend (second terminal)
    cd frontend && npm install && npm run dev

## Tests
    cd backend && python -m pytest tests/ -v
    cd frontend && npm test

## Limits
20 MB max, 100 pages max, 10 conversions/hour/IP. Digital PDFs only (no OCR).

## Deploy
1. Push to GitHub.
2. Render: "New > Blueprint" pointing at this repo (`render.yaml`). Note the service URL.
3. Vercel: import repo, root directory `frontend/`, add env var `VITE_API_URL=<render URL>`.
4. Back in Render, set `ALLOWED_ORIGINS=<vercel URL>`.
```

- [ ] **Step 2: Deploy backend to Render**

Push the repo to GitHub, create a Render Blueprint from it. Verify:

```bash
curl -s https://<render-service>.onrender.com/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Deploy frontend to Vercel**

Create `frontend/.env.production`:

```
VITE_API_URL=https://<render-service>.onrender.com
```

Import the repo in Vercel with root directory `frontend/`. After deploy, set `ALLOWED_ORIGINS` in Render to the Vercel production URL and redeploy the backend service.

- [ ] **Step 4: Manual E2E checklist (production)**

- [ ] Simple text PDF converts; .docx opens in Word/Google Docs with editable text
- [ ] Multi-column PDF converts (fidelity may vary — acceptable)
- [ ] PDF with a table converts; table is editable
- [ ] Password-protected PDF → "Password-protected PDFs aren't supported."
- [ ] Scanned PDF → scanned-PDF message
- [ ] 25 MB file → rejected client-side before upload
- [ ] Non-PDF renamed to `.pdf` → "That file isn't a PDF."
- [ ] 11th conversion within an hour → rate-limit message
- [ ] Browser devtools: no CORS errors from the production domain

- [ ] **Step 5: Commit**

```bash
git add README.md frontend/.env.production
git commit -m "docs: README, deploy config, and E2E checklist"
```
