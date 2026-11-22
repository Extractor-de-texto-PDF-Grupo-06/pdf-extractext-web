"""Adaptador del puerto Extractor: llama al extractor a través de Traefik (ADR 0005)."""

import logging

import httpx

from app.application.entities import Extraction
from app.application.errors import ExtractorUnavailable, FileTooLarge, InvalidPdf

logger = logging.getLogger(__name__)

_DEFAULT_INVALID_DETAIL = "El PDF es inválido, está corrupto o tiene contraseña."


class HttpExtractor:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/extract"

    async def extract(self, pdf: bytes, timeout_seconds: float) -> Extraction:
        try:
            response = await self._client.post(
                self._url,
                content=pdf,
                headers={"Content-Type": "application/pdf"},
                timeout=timeout_seconds,
            )
        except httpx.TransportError as error:
            logger.warning("No se pudo llegar al extractor: %s", type(error).__name__)
            raise ExtractorUnavailable() from error

        if response.status_code == 422:
            raise InvalidPdf(_detail(response) or _DEFAULT_INVALID_DETAIL)
        if response.status_code == 413:
            raise FileTooLarge()
        if response.status_code != 200:
            logger.warning("El extractor respondió %s", response.status_code)
            raise ExtractorUnavailable()
        return _to_extraction(response)


def _to_extraction(response: httpx.Response) -> Extraction:
    """Valida el contrato; ``metadata`` es opcional para tolerar un extractor anterior a T6."""
    try:
        body = response.json()
    except ValueError as error:
        raise ExtractorUnavailable() from error
    content = body.get("content") if isinstance(body, dict) else None
    page_count = body.get("page_count") if isinstance(body, dict) else None
    if not isinstance(content, str) or type(page_count) is not int or page_count < 1:
        logger.warning("El extractor devolvió una respuesta fuera del contrato")
        raise ExtractorUnavailable()
    metadata = body.get("metadata")
    return Extraction(
        content=content,
        page_count=page_count,
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _detail(response: httpx.Response) -> str | None:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return None
    return detail if isinstance(detail, str) else None
