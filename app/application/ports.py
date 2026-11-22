"""Puertos: lo que los casos de uso necesitan de los otros servicios."""

from typing import Any, Protocol

from app.application.entities import Extraction, NewDocument, ProxiedResponse, WebConfig


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


class DocumentsProxy(Protocol):
    async def forward(
        self, method: str, path: str, query: dict[str, str], body: bytes | None
    ) -> ProxiedResponse:
        """Reenvía el pedido del CRUD a documents y devuelve su respuesta sin cambios.
        Lanza ``DocumentsUnavailable`` si documents no responde."""
        ...


class DependencyHealth(Protocol):
    async def check(self) -> dict[str, bool]:
        """Si cada servicio del que depende web responde a su ``/health``."""
        ...


class ConfigSource(Protocol):
    async def get(self) -> WebConfig:
        """La configuración vigente. Nunca falla: si no puede leerla, usa la de respaldo."""
        ...
