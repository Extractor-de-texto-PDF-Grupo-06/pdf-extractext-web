"""Puertos: lo que los casos de uso necesitan de los otros servicios."""

from typing import Any, Protocol

from app.application.entities import Extraction, NewDocument, WebConfig


class Extractor(Protocol):
    async def extract(self, pdf: bytes, timeout_seconds: float) -> Extraction:
        """Lanza ``InvalidPdf`` o ``FileTooLarge`` si el problema es el PDF, y
        ``ExtractorUnavailable`` si el extractor no pudo responder."""
        ...


class DocumentStore(Protocol):
    """Lanza ``DocumentsUnavailable`` si documents no responde."""

    async def find_by_checksum(self, checksum: str) -> dict[str, Any] | None: ...

    async def create(self, document: NewDocument) -> dict[str, Any]:
        """Devuelve el documento guardado. Lanza ``DuplicateDocument`` si el checksum ya existe."""
        ...


class ConfigSource(Protocol):
    async def get(self) -> WebConfig:
        """La configuración vigente. Nunca falla: si no puede leerla, usa la de respaldo."""
        ...
