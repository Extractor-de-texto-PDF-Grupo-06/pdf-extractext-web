"""Dobles de los puertos de application, para probar sin red."""

from dataclasses import asdict

from app.application.entities import Extraction, NewDocument, ProxiedResponse, WebConfig
from app.application.errors import DuplicateDocument

DEFAULT_CONFIG = WebConfig(
    max_file_size_mb=10,
    extractor_timeout_seconds=30.0,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_seconds=30.0,
)


class FakeExtractor:
    """Devuelve ``result`` o lanza ``error``; anota cada llamada."""

    def __init__(self, result: Extraction | None = None, error: Exception | None = None) -> None:
        self.result = result or Extraction(content="# Hola", page_count=1, metadata={})
        self.error = error
        self.calls: list[tuple[bytes, float]] = []

    async def extract(self, pdf: bytes, timeout_seconds: float) -> Extraction:
        self.calls.append((pdf, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result


class FakeDocuments:
    """Guarda los documentos por checksum, con el índice único de documents."""

    def __init__(self) -> None:
        self.saved: dict[str, dict] = {}
        self.error: Exception | None = None
        self.race_with: dict | None = None

    async def find_by_checksum(self, checksum: str) -> dict | None:
        if self.error is not None:
            raise self.error
        return self.saved.get(checksum)

    async def create(self, document: NewDocument) -> dict:
        if self.error is not None:
            raise self.error
        if self.race_with is not None:
            # Otra subida del mismo PDF guardó entre la consulta y el alta.
            self.saved[document.checksum] = self.race_with
        if document.checksum in self.saved:
            raise DuplicateDocument()
        created = {"id": f"doc-{len(self.saved) + 1}", **asdict(document)}
        self.saved[document.checksum] = created
        return created


class FixedConfig:
    def __init__(self, config: WebConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    async def get(self) -> WebConfig:
        return self.config


class FakeDocumentsProxy:
    """Responde ``answer`` a cualquier pedido reenviado; anota cada uno."""

    def __init__(self) -> None:
        self.answer = ProxiedResponse(200, b'{"data": []}', "application/json")
        self.error: Exception | None = None
        self.requests: list[tuple[str, str, dict, bytes | None]] = []

    async def forward(
        self, method: str, path: str, query: dict[str, str], body: bytes | None
    ) -> ProxiedResponse:
        self.requests.append((method, path, query, body))
        if self.error is not None:
            raise self.error
        return self.answer


class FakeHealth:
    def __init__(self, services: dict[str, bool] | None = None) -> None:
        self.services = services or {"documents": True, "extractor": True, "config": True}

    async def check(self) -> dict[str, bool]:
        return self.services
