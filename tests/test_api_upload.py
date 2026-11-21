"""Contrato HTTP de la subida (POST /api/documents), con los otros servicios reemplazados por dobles."""

import tempfile
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app.application.circuit_breaker import CircuitBreaker
from app.application.entities import WebConfig
from app.application.errors import DocumentsUnavailable, ExtractorUnavailable, InvalidPdf
from app.application.use_cases import UploadDocument
from app.main import create_app
from app.presentation.state import Services
from tests.fakes import FakeDocuments, FakeExtractor, FixedConfig

PDF = b"%PDF-1.4 hola"
PDF_CHECKSUM = "bc39ce0612bcde4063a33a16c57c873efbc5c908b15a747c801cb4bc0813688f"


@pytest.fixture
def extractor():
    return FakeExtractor()


@pytest.fixture
def documents():
    return FakeDocuments()


@pytest.fixture
def config():
    return FixedConfig()


@pytest.fixture
def client(extractor, documents, config):
    upload = UploadDocument(extractor, documents, config, CircuitBreaker("extractor"))
    app = create_app(lambda: nullcontext(Services(upload=upload)))
    with TestClient(app) as client:
        yield client


def post_pdf(client, data=PDF, filename="informe.pdf", content_type="application/pdf"):
    return client.post("/api/documents", files={"file": (filename, data, content_type)})


def test_la_subida_responde_201_con_el_documento_guardado(client):
    response = post_pdf(client)

    assert response.status_code == 201
    assert response.json() == {
        "id": "doc-1",
        "filename": "informe.pdf",
        "checksum": PDF_CHECKSUM,
        "text": "# Hola",
        "page_count": 1,
        "metadata": {},
    }


def test_sin_el_campo_file_responde_400(client):
    response = client.post("/api/documents", files={"otro": ("informe.pdf", PDF, "application/pdf")})

    assert response.status_code == 400
    assert response.json() == {"detail": "Falta el archivo PDF en el campo 'file'."}


def test_un_pedido_que_no_es_multipart_responde_400(client):
    response = client.post("/api/documents", json={"file": "informe.pdf"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "El PDF tiene que llegar como multipart/form-data en el campo 'file'."
    }


def test_un_archivo_sin_extension_pdf_responde_400(client):
    response = post_pdf(client, filename="informe.txt")

    assert response.status_code == 400
    assert response.json() == {"detail": "El archivo debe tener extensión .pdf."}


def test_un_content_type_que_no_es_pdf_responde_415(client):
    response = post_pdf(client, content_type="text/plain")

    assert response.status_code == 415


def test_un_archivo_mas_grande_que_el_limite_responde_413(client, config, extractor):
    config.config = WebConfig(1, 30.0, 5, 30.0)

    response = post_pdf(client, data=b"%" * 1_048_577)

    assert response.status_code == 413
    assert response.json() == {"detail": "El archivo supera el tamaño máximo de 1 MB."}
    assert extractor.calls == []


def test_un_pdf_ya_guardado_responde_409(client):
    post_pdf(client)

    response = post_pdf(client)

    assert response.status_code == 409
    assert response.json() == {"detail": "Ese PDF ya está guardado."}


def test_un_pdf_invalido_responde_422_con_el_motivo_del_extractor(client, extractor):
    extractor.error = InvalidPdf("El archivo PDF está protegido con contraseña.")

    response = post_pdf(client)

    assert response.status_code == 422
    assert response.json() == {"detail": "El archivo PDF está protegido con contraseña."}


def test_si_el_extractor_falla_responde_502(client, extractor):
    extractor.error = ExtractorUnavailable()

    response = post_pdf(client)

    assert response.status_code == 502


def test_con_el_circuito_abierto_responde_503_con_retry_after(client, extractor):
    extractor.error = ExtractorUnavailable()
    for _ in range(5):
        assert post_pdf(client).status_code == 502

    response = post_pdf(client)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert len(extractor.calls) == 5


def test_si_documents_falla_responde_502(client, documents):
    documents.error = DocumentsUnavailable()

    response = post_pdf(client)

    assert response.status_code == 502


def test_el_pdf_nunca_se_escribe_a_disco(client, monkeypatch):
    def no_disk(*args, **kwargs):
        raise AssertionError("El PDF no se puede escribir a disco")

    for name in ("SpooledTemporaryFile", "TemporaryFile", "NamedTemporaryFile", "mkstemp"):
        monkeypatch.setattr(tempfile, name, no_disk)
    two_megabytes = b"%PDF-1.4 " + b"x" * 2_097_152

    response = post_pdf(client, data=two_megabytes)

    assert response.status_code == 201
    assert response.json()["checksum"] == (
        "984ab23c0ba0e8ca47aa6b45a82e009b29c6b8a31f0cf4939ecbdad24012ec66"
    )


def test_health_responde_200_mientras_el_proceso_vive(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
