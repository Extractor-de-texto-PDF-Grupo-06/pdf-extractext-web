"""Entidades de la subida."""

from dataclasses import dataclass, field

_BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class PdfFile:
    """El PDF que sube el usuario. Vive solo en memoria."""

    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class Extraction:
    """Lo que devuelve el extractor: el texto en Markdown, las páginas y los metadatos."""

    content: str
    page_count: int
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NewDocument:
    """El alta que se le pide a documents."""

    filename: str
    checksum: str
    text: str
    page_count: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class WebConfig:
    """Los valores de web que pueden cambiar en caliente desde la configuración centralizada."""

    max_file_size_mb: int
    extractor_timeout_seconds: float
    circuit_breaker_failure_threshold: int
    circuit_breaker_recovery_seconds: float

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_size_mb * _BYTES_PER_MB
