# PDF to Word Converter

Free web tool that converts digital PDFs to editable .docx. Files are never stored.

## Stack

- `frontend/` — React + Vite + Tailwind (Vercel)
- `backend/` — FastAPI + pdf2docx (Docker on Render)

## Local development

```bash
# backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

```bash
# frontend (second terminal)
cd frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && python -m pytest tests/ -v
cd frontend && npm test
```

## Limits

20 MB max, 100 pages max, 10 conversions/hour/IP. Digital PDFs only (no OCR).

## Deploy

1. Push to GitHub.
2. Render: "New > Blueprint" pointing at this repo (`render.yaml`). Note the service URL.
3. Vercel: import repo, root directory `frontend/`, add env var `VITE_API_URL=<render URL>`.
   (Copy `frontend/.env.production.example` to `.env.production` with your real Render URL, or set `VITE_API_URL` in Vercel's env settings — the Vercel env var is the recommended way.)
4. Back in Render, set `ALLOWED_ORIGINS=<vercel URL>`.

## Manual E2E checklist (run after deploy)

- [ ] Simple text PDF converts; .docx opens in Word/Google Docs with editable text
- [ ] Multi-column PDF converts (fidelity may vary — acceptable)
- [ ] PDF with a table converts; table is editable
- [ ] Password-protected PDF → "Password-protected PDFs aren't supported."
- [ ] Scanned PDF → scanned-PDF message
- [ ] 25 MB file → rejected client-side before upload
- [ ] Non-PDF renamed to `.pdf` → "That file isn't a PDF."
- [ ] 11th conversion within an hour → rate-limit message
- [ ] Browser devtools: no CORS errors from the production domain
