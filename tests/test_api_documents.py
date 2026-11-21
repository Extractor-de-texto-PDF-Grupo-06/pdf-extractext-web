"""CRUD reenviado a documents, estado de los servicios e interfaz."""

from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app.application.circuit_breaker import CircuitBreaker
from app.application.entities import ProxiedResponse
from app.application.errors import DocumentsUnavailable
from app.application.use_cases import UploadDocument
from app.main import create_app
from app.presentation.state import Services
from tests.fakes import FakeDocuments, FakeDocumentsProxy, FakeExtractor, FakeHealth, FixedConfig


@pytest.fixture
def proxy():
    return FakeDocumentsProxy()


@pytest.fixture
def health():
    return FakeHealth()


@pytest.fixture
def client(proxy, health):
    upload = UploadDocument(FakeExtractor(), FakeDocuments(), FixedConfig(), CircuitBreaker("x"))
    app = create_app(lambda: nullcontext(Services(upload=upload, documents=proxy, health=health)))
    with TestClient(app) as client:
        yield client


def test_listar_reenvia_a_documents_con_la_paginacion(client, proxy):
    proxy.answer = ProxiedResponse(200, b'{"data": [{"id": "doc-1"}]}', "application/json")

    response = client.get("/api/documents", params={"skip": "10", "limit": "5"})

    assert response.status_code == 200
    assert response.json() == {"data": [{"id": "doc-1"}]}
    assert proxy.requests == [("GET", "/", {"skip": "10", "limit": "5"}, None)]


def test_ver_un_documento_reenvia_su_id(client, proxy):
    proxy.answer = ProxiedResponse(200, b'{"id": "doc-1", "text": "# Hola"}', "application/json")

    response = client.get("/api/documents/doc-1")

    assert response.json() == {"id": "doc-1", "text": "# Hola"}
    assert proxy.requests == [("GET", "/doc-1", {}, None)]


def test_los_errores_de_documents_llegan_igual_al_navegador(client, proxy):
    proxy.answer = ProxiedResponse(404, b'{"detail": "Documento no encontrado."}', "application/json")

    response = client.get("/api/documents/no-existe")

    assert response.status_code == 404
    assert response.json() == {"detail": "Documento no encontrado."}


def test_editar_reenvia_el_cuerpo(client, proxy):
    proxy.answer = ProxiedResponse(200, b'{"id": "doc-1", "filename": "nuevo.pdf"}', "application/json")

    response = client.put("/api/documents/doc-1", json={"filename": "nuevo.pdf"})

    assert response.status_code == 200
    method, path, query, body = proxy.requests[0]
    assert (method, path, query) == ("PUT", "/doc-1", {})
    assert body == b'{"filename":"nuevo.pdf"}'


def test_borrar_reenvia_y_responde_204_sin_cuerpo(client, proxy):
    proxy.answer = ProxiedResponse(204, b"", "")

    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 204
    assert response.content == b""
    assert proxy.requests == [("DELETE", "/doc-1", {}, None)]


def test_si_documents_no_responde_el_crud_responde_502(client, proxy):
    proxy.error = DocumentsUnavailable()

    response = client.get("/api/documents")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "El servicio de documentos no respondió. Intentá de nuevo en unos segundos."
    }


def test_api_health_informa_el_estado_de_cada_servicio(client, health):
    health.services = {"documents": True, "extractor": False, "config": True}

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "services": {"documents": "ok", "extractor": "down", "config": "ok"},
    }


def test_api_health_esta_ok_si_todos_responden(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_la_raiz_sirve_la_interfaz(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<script src=\"app.js\"></script>" in response.text


def test_la_interfaz_usa_la_api_de_web(client):
    script = client.get("/app.js").text

    assert "const API_URL = '/api';" in script
    assert "/api/v1" not in script
    assert "/extract" not in script
