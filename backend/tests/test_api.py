from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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


def test_convert_rejects_too_large(text_pdf):
    padded = text_pdf + b"\0" * (20 * 1024 * 1024)
    resp = _upload(padded)
    assert resp.status_code == 413
    assert resp.json()["code"] == "TOO_LARGE"


def test_convert_conversion_failure_returns_500(monkeypatch, text_pdf):
    from app import main as main_module
    from app.converter import ConversionError

    def boom(_):
        raise ConversionError("kaboom")

    monkeypatch.setattr(main_module, "convert_pdf_to_docx", boom)
    resp = _upload(text_pdf)
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "CONVERSION_FAILED"
    assert "kaboom" not in body["message"]


def test_filename_with_quote_is_sanitized(text_pdf):
    resp = _upload(text_pdf, 'we"ird.pdf')
    assert resp.status_code == 200
    assert '"' not in resp.headers["content-disposition"].replace('filename="', "").replace('.docx"', "")
    assert "weird.docx" in resp.headers["content-disposition"]
