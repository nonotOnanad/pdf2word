# PDF-to-Word Web Converter — Design Spec

**Date:** 2026-07-20
**Status:** Approved by user (pending final spec review)

## Overview

A public, free web app that converts digitally-created PDFs into editable Word (.docx) files. Self-hosted conversion engine (pdf2docx) — no per-conversion API costs. Files are processed in-memory/temp and never stored.

**Out of scope for v1:** scanned-PDF OCR, user accounts, payment tiers, batch conversion, async job queue.

## Requirements

- Public free tool; no login.
- Digital PDFs only (real text layer). Scanned PDFs are detected and rejected with a clear message.
- Upload limits: max 20 MB file size, max 100 pages.
- Abuse protection: per-IP rate limiting (10 conversions/hour), 120s request timeout.
- Privacy guarantee: no persistence of uploaded or converted files.

## Architecture

Two deployables:

1. **Frontend** — React + Vite + Tailwind SPA, hosted on Vercel.
2. **Backend** — FastAPI (Python) in a Docker container on Render or Railway free tier.

The frontend calls the backend over HTTPS with CORS restricted to the frontend origin. No database, no object storage. Conversion is synchronous within the HTTP request (Option A), which is safe given the size/page caps.

## Components

### Frontend (single page)

- Drag-and-drop upload zone (react-dropzone) plus file picker.
- Client-side pre-checks: `.pdf` extension, size ≤ 20 MB.
- UI states: idle → uploading → converting → done (download button) → error.
- Inline error messages mapped from API error codes, including rate-limit notice.
- Static copy: "Your files are never stored."

### Backend

- `POST /api/convert` — multipart PDF upload:
  1. Validate magic bytes (`%PDF`), size ≤ 20 MB.
  2. Open with PyMuPDF: reject encrypted PDFs; reject page count > 100; detect missing text layer (scanned) via text extraction and reject with a specific error.
  3. Write to a per-request temp directory.
  4. Convert with `pdf2docx.Converter`.
  5. Stream the .docx back as the response.
  6. Delete temp files in a `finally` block (guaranteed cleanup on success or failure).
- `GET /api/health` — uptime check.
- Rate limiting via slowapi (per-IP, 10/hour). Worker pool sized to the free-tier container so concurrent conversions queue instead of exhausting memory.

## Data Flow

Browser → upload PDF → validate → convert → stream .docx → temp files deleted. Nothing persists beyond the request lifecycle.

## Error Handling

| Case | Response | User message |
|---|---|---|
| Not a PDF | 400 | "That file isn't a PDF." |
| Too large | 413 | "Max file size is 20 MB." |
| Too many pages | 400 | "Max 100 pages." |
| Encrypted PDF | 400 | "Password-protected PDFs aren't supported." |
| Scanned / no text layer | 422 | "This looks like a scanned PDF — OCR isn't supported yet." |
| Rate limited | 429 | "Hourly limit reached — try again later." |
| Conversion failure | 500 | "We couldn't convert this PDF." (no internal details leaked) |

Temp cleanup is guaranteed in all paths.

## Testing

- **Backend (pytest):** fixture PDFs — simple text, multi-column, tables, images, encrypted, scanned, oversized, corrupt/non-PDF. Assert status codes, that output opens with python-docx, and that the temp dir is empty after each request.
- **Frontend:** component tests for the upload flow states; manual E2E pass before deploy.

## Deployment

- Frontend: Vercel (auto-deploy from Git).
- Backend: Dockerfile deployed to Render/Railway free tier; health check wired to `/api/health`.
- CORS locked to the production frontend domain (plus localhost for dev).

## Future Extensions (explicitly deferred)

- OCR pipeline (Tesseract) for scanned PDFs.
- Async job queue if limits are raised.
- Optional premium tier using a commercial API (Adobe) for high-fidelity conversion.
