"""Adaptadores HTTP del extractor y de documents, con httpx.MockTransport (sin red)."""

import json

import httpx
import pytest

from app.application.entities import Extraction, NewDocument
from app.application.errors import (
    DocumentsUnavailable,
    DuplicateDocument,
    ExtractorUnavailable,
    FileTooLarge,
    InvalidPdf,
)
from app.infrastructure.http_documents import HttpDocuments
from app.infrastructure.http_extractor import HttpExtractor

pytestmark = pytest.mark.anyio

NEW_DOCUMENT = NewDocument(
    filename="informe.pdf", checksum="ab" * 32, text="# Hola", page_count=2, metadata={"author": "Ana"}
)


def client_answering(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def failing_with(error: type[httpx.TransportError]):
    def handler(request):
        raise error("sin conexión", request=request)

    return handler


# ── Extractor ─────────────────────────────────────────────────────────


async def test_el_extractor_recibe_el_pdf_crudo_con_el_timeout_pedido():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        seen["timeout"] = request.extensions["timeout"]["read"]
        return httpx.Response(200, json={"content": "# Hola", "page_count": 2, "metadata": {}})

    async with client_answering(handler) as client:
        await HttpExtractor(client, "http://traefik:8081/extractor/").extract(b"%PDF-1.4", 12.0)

    assert seen == {
        "url": "http://traefik:8081/extractor/extract",
        "content_type": "application/pdf",
        "body": b"%PDF-1.4",
        "timeout": 12.0,
    }


async def test_el_extractor_devuelve_texto_paginas_y_metadatos():
    body = {"content": "# Hola", "page_count": 2, "metadata": {"author": "Ana"}}

    async with client_answering(lambda request: httpx.Response(200, json=body)) as client:
        extraction = await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)

    assert extraction == Extraction(content="# Hola", page_count=2, metadata={"author": "Ana"})


async def test_si_el_extractor_no_devuelve_metadatos_quedan_vacios():
    body = {"content": "# Hola", "page_count": 2}

    async with client_answering(lambda request: httpx.Response(200, json=body)) as client:
        extraction = await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)

    assert extraction.metadata == {}


async def test_un_422_del_extractor_es_un_pdf_invalido_con_su_motivo():
    answer = httpx.Response(422, json={"detail": "El archivo PDF está corrupto."})

    async with client_answering(lambda request: answer) as client:
        with pytest.raises(InvalidPdf, match="El archivo PDF está corrupto."):
            await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)


async def test_un_413_del_extractor_es_un_archivo_demasiado_grande():
    async with client_answering(lambda request: httpx.Response(413)) as client:
        with pytest.raises(FileTooLarge):
            await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_un_error_del_servidor_es_un_extractor_caido(status):
    async with client_answering(lambda request: httpx.Response(status)) as client:
        with pytest.raises(ExtractorUnavailable):
            await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
async def test_sin_conexion_o_sin_respuesta_es_un_extractor_caido(error):
    async with client_answering(failing_with(error)) as client:
        with pytest.raises(ExtractorUnavailable):
            await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)


@pytest.mark.parametrize(
    "body", [{"page_count": 2}, {"content": "x", "page_count": 0}, {"content": 1, "page_count": 2}]
)
async def test_una_respuesta_fuera_del_contrato_es_un_extractor_caido(body):
    async with client_answering(lambda request: httpx.Response(200, json=body)) as client:
        with pytest.raises(ExtractorUnavailable):
            await HttpExtractor(client, "http://extractor").extract(b"%PDF", 30.0)


# ── Documents ─────────────────────────────────────────────────────────


async def test_buscar_por_checksum_devuelve_el_documento():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"data": [{"id": "doc-1"}]})

    async with client_answering(handler) as client:
        found = await HttpDocuments(client, "http://documents:8000").find_by_checksum("ab" * 32)

    assert found == {"id": "doc-1"}
    assert seen["url"] == f"http://documents:8000/?checksum={'ab' * 32}"


async def test_buscar_un_checksum_que_no_existe_devuelve_none():
    async with client_answering(lambda request: httpx.Response(200, json={"data": []})) as client:
        assert await HttpDocuments(client, "http://documents").find_by_checksum("ab" * 32) is None


async def test_el_alta_manda_el_documento_y_devuelve_el_guardado():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "doc-1", "filename": "informe.pdf"})

    async with client_answering(handler) as client:
        created = await HttpDocuments(client, "http://documents/").create(NEW_DOCUMENT)

    assert created == {"id": "doc-1", "filename": "informe.pdf"}
    assert seen == {
        "method": "POST",
        "url": "http://documents/",
        "body": {
            "filename": "informe.pdf",
            "checksum": "ab" * 32,
            "text": "# Hola",
            "page_count": 2,
            "metadata": {"author": "Ana"},
        },
    }


async def test_un_409_en_el_alta_es_un_duplicado():
    async with client_answering(lambda request: httpx.Response(409)) as client:
        with pytest.raises(DuplicateDocument):
            await HttpDocuments(client, "http://documents").create(NEW_DOCUMENT)


@pytest.mark.parametrize("status", [422, 500, 503])
async def test_otra_respuesta_en_el_alta_es_documents_caido(status):
    async with client_answering(lambda request: httpx.Response(status)) as client:
        with pytest.raises(DocumentsUnavailable):
            await HttpDocuments(client, "http://documents").create(NEW_DOCUMENT)


async def test_un_error_al_buscar_es_documents_caido():
    async with client_answering(lambda request: httpx.Response(500)) as client:
        with pytest.raises(DocumentsUnavailable):
            await HttpDocuments(client, "http://documents").find_by_checksum("ab" * 32)


async def test_sin_conexion_documents_esta_caido():
    async with client_answering(failing_with(httpx.ConnectError)) as client:
        with pytest.raises(DocumentsUnavailable):
            await HttpDocuments(client, "http://documents").find_by_checksum("ab" * 32)
