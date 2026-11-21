"""Caso de uso UploadDocument: el flujo de la subida, con los puertos reemplazados por dobles."""

import pytest

from app.application.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.application.entities import Extraction, NewDocument, PdfFile, WebConfig
from app.application.errors import (
    DocumentsUnavailable,
    DuplicateDocument,
    ExtractorUnavailable,
    FileTooLarge,
    InvalidPdf,
    NotAPdfName,
    UnsupportedMediaType,
)
from app.application.use_cases import UploadDocument
from tests.fakes import DEFAULT_CONFIG, FakeDocuments, FakeExtractor, FixedConfig

pytestmark = pytest.mark.anyio

PDF = PdfFile(filename="informe.pdf", content_type="application/pdf", data=b"%PDF-1.4 hola")
PDF_CHECKSUM = "bc39ce0612bcde4063a33a16c57c873efbc5c908b15a747c801cb4bc0813688f"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def extractor():
    return FakeExtractor(Extraction(content="# Hola", page_count=2, metadata={"author": "Ana"}))


@pytest.fixture
def documents():
    return FakeDocuments()


@pytest.fixture
def config():
    return FixedConfig()


@pytest.fixture
def breaker():
    return CircuitBreaker("extractor", clock=FakeClock())


@pytest.fixture
def upload(extractor, documents, config, breaker):
    return UploadDocument(extractor, documents, config, breaker)


async def test_guarda_el_documento_extraido_y_lo_devuelve(upload, documents):
    created = await upload.execute(PDF)

    assert created == {
        "id": "doc-1",
        "filename": "informe.pdf",
        "checksum": PDF_CHECKSUM,
        "text": "# Hola",
        "page_count": 2,
        "metadata": {"author": "Ana"},
    }
    assert PDF_CHECKSUM in documents.saved


async def test_le_pasa_al_extractor_el_pdf_y_el_timeout_de_la_configuracion(upload, extractor):
    await upload.execute(PDF)

    assert extractor.calls == [(b"%PDF-1.4 hola", 30.0)]


async def test_rechaza_un_archivo_sin_extension_pdf(upload, extractor):
    with pytest.raises(NotAPdfName):
        await upload.execute(PdfFile("informe.txt", "application/pdf", b"%PDF-1.4 hola"))
    assert extractor.calls == []


async def test_acepta_la_extension_en_mayusculas(upload):
    created = await upload.execute(PdfFile("INFORME.PDF", "application/pdf", b"%PDF-1.4 hola"))

    assert created["filename"] == "INFORME.PDF"


async def test_rechaza_un_content_type_que_no_es_pdf(upload, extractor):
    with pytest.raises(UnsupportedMediaType):
        await upload.execute(PdfFile("informe.pdf", "text/plain", b"%PDF-1.4 hola"))
    assert extractor.calls == []


@pytest.mark.parametrize("content_type", ["", "application/octet-stream"])
async def test_acepta_un_content_type_generico(upload, content_type):
    created = await upload.execute(PdfFile("informe.pdf", content_type, b"%PDF-1.4 hola"))

    assert created["checksum"] == PDF_CHECKSUM


async def test_rechaza_un_archivo_mas_grande_que_el_limite(upload, config, extractor):
    config.config = WebConfig(1, 30.0, 5, 30.0)

    with pytest.raises(FileTooLarge):
        await upload.execute(PdfFile("informe.pdf", "application/pdf", b"%" * 1_048_577))
    assert extractor.calls == []


async def test_acepta_un_archivo_justo_en_el_limite(upload, config):
    config.config = WebConfig(1, 30.0, 5, 30.0)

    created = await upload.execute(PdfFile("informe.pdf", "application/pdf", b"%" * 1_048_576))

    assert created["page_count"] == 2


async def test_el_limite_de_tamano_sale_de_la_configuracion(upload, config):
    assert await upload.max_file_bytes() == 10_485_760

    config.config = WebConfig(2, 30.0, 5, 30.0)

    assert await upload.max_file_bytes() == 2_097_152


async def test_un_pdf_ya_guardado_es_duplicado_y_no_se_extrae(upload, documents, extractor):
    documents.saved[PDF_CHECKSUM] = {"id": "doc-viejo"}

    with pytest.raises(DuplicateDocument):
        await upload.execute(PDF)
    assert extractor.calls == []


async def test_si_otra_subida_guardo_el_mismo_pdf_antes_es_duplicado(upload, documents):
    documents.race_with = {"id": "doc-de-la-otra-subida"}

    with pytest.raises(DuplicateDocument):
        await upload.execute(PDF)


async def test_un_pdf_invalido_no_se_guarda(upload, extractor, documents):
    extractor.error = InvalidPdf("El archivo PDF está corrupto.")

    with pytest.raises(InvalidPdf):
        await upload.execute(PDF)
    assert documents.saved == {}


async def test_los_pdfs_invalidos_no_abren_el_circuito(upload, extractor, breaker):
    extractor.error = InvalidPdf("El archivo PDF está corrupto.")

    for _ in range(6):
        with pytest.raises(InvalidPdf):
            await upload.execute(PDF)

    assert len(extractor.calls) == 6


async def test_con_el_extractor_caido_la_sexta_subida_no_lo_llama(upload, extractor):
    extractor.error = ExtractorUnavailable()
    for _ in range(5):
        with pytest.raises(ExtractorUnavailable):
            await upload.execute(PDF)

    with pytest.raises(CircuitOpenError) as error:
        await upload.execute(PDF)

    assert len(extractor.calls) == 5
    assert error.value.retry_after == 30.0


async def test_el_umbral_del_circuito_sale_de_la_configuracion(upload, extractor, config):
    config.config = WebConfig(10, 30.0, 2, 15.0)
    extractor.error = ExtractorUnavailable()
    for _ in range(2):
        with pytest.raises(ExtractorUnavailable):
            await upload.execute(PDF)

    with pytest.raises(CircuitOpenError) as error:
        await upload.execute(PDF)

    assert len(extractor.calls) == 2
    assert error.value.retry_after == 15.0


async def test_si_documents_no_responde_no_se_extrae(upload, documents, extractor):
    documents.error = DocumentsUnavailable()

    with pytest.raises(DocumentsUnavailable):
        await upload.execute(PDF)
    assert extractor.calls == []


async def test_el_alta_lleva_los_datos_de_la_extraccion(documents, config, breaker):
    extractor = FakeExtractor(Extraction(content="texto", page_count=3, metadata={}))
    upload = UploadDocument(extractor, documents, config, breaker)

    await upload.execute(PDF)

    saved = documents.saved[PDF_CHECKSUM]
    assert NewDocument(**{key: saved[key] for key in saved if key != "id"}) == NewDocument(
        filename="informe.pdf", checksum=PDF_CHECKSUM, text="texto", page_count=3, metadata={}
    )


def test_la_configuracion_por_defecto_es_la_de_la_especificacion():
    assert DEFAULT_CONFIG.max_file_bytes == 10_485_760
