"""Caso de uso de la subida: validar, evitar duplicados, extraer y guardar."""

import hashlib
from typing import Any

from app.application.circuit_breaker import CircuitBreaker
from app.application.entities import Extraction, NewDocument, PdfFile, WebConfig
from app.application.errors import (
    DuplicateDocument,
    ExtractorUnavailable,
    FileTooLarge,
    InvalidPdf,
    NotAPdfName,
    UnsupportedMediaType,
)
from app.application.ports import ConfigSource, DocumentStore, Extractor

_PDF_MEDIA_TYPE = "application/pdf"
# Tipos que mandan los clientes que no declaran un MIME real (curl, algunos navegadores).
# No se rechazan: el contenido lo valida el extractor por la firma %PDF.
_GENERIC_MEDIA_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})


class UploadDocument:
    """Subir un PDF. Solo conoce puertos, no librerías."""

    def __init__(
        self,
        extractor: Extractor,
        documents: DocumentStore,
        config: ConfigSource,
        breaker: CircuitBreaker,
    ) -> None:
        self._extractor = extractor
        self._documents = documents
        self._config = config
        self._breaker = breaker

    async def max_file_bytes(self) -> int:
        """El tamaño máximo vigente, para no leer más que eso del pedido."""
        return (await self._config.get()).max_file_bytes

    async def execute(self, pdf: PdfFile) -> dict[str, Any]:
        config = await self._config.get()
        _validate(pdf, config)
        checksum = hashlib.sha256(pdf.data).hexdigest()
        # Atajo para no extraer en vano; la garantía es el índice único de documents.
        if await self._documents.find_by_checksum(checksum) is not None:
            raise DuplicateDocument()
        extraction = await self._extract(pdf.data, config)
        return await self._documents.create(
            NewDocument(
                filename=pdf.filename,
                checksum=checksum,
                text=extraction.content,
                page_count=extraction.page_count,
                metadata=extraction.metadata,
            )
        )

    async def _extract(self, data: bytes, config: WebConfig) -> Extraction:
        """Llama al extractor detrás del circuit breaker. Solo sus fallos abren el circuito."""
        self._breaker.configure(
            config.circuit_breaker_failure_threshold, config.circuit_breaker_recovery_seconds
        )
        self._breaker.before_call()
        try:
            extraction = await self._extractor.extract(data, config.extractor_timeout_seconds)
        except ExtractorUnavailable:
            self._breaker.record_failure()
            raise
        except (InvalidPdf, FileTooLarge):
            # El extractor respondió bien: el problema es el PDF.
            self._breaker.record_success()
            raise
        except BaseException:
            # Cancelada o con un error inesperado: no es éxito ni fallo del extractor.
            self._breaker.release()
            raise
        self._breaker.record_success()
        return extraction


def _validate(pdf: PdfFile, config: WebConfig) -> None:
    if not pdf.filename.lower().endswith(".pdf"):
        raise NotAPdfName()
    media_type = pdf.content_type.lower()
    if media_type != _PDF_MEDIA_TYPE and media_type not in _GENERIC_MEDIA_TYPES:
        raise UnsupportedMediaType()
    if len(pdf.data) > config.max_file_bytes:
        raise FileTooLarge(config.max_file_size_mb)
