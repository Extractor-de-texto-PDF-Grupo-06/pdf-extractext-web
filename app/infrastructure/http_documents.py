"""Adaptador de los puertos DocumentStore y DocumentsProxy: llama a documents por la red
interna de Docker."""

import logging
from dataclasses import asdict
from typing import Any

import httpx

from app.application.entities import NewDocument, ProxiedResponse
from app.application.errors import DocumentsUnavailable, DuplicateDocument

logger = logging.getLogger(__name__)


class HttpDocuments:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def find_by_checksum(self, checksum: str) -> dict[str, Any] | None:
        response = await self._send("GET", "/", params={"checksum": checksum})
        if response.status_code != 200:
            raise _unavailable(response)
        found = response.json().get("data", [])
        return found[0] if found else None

    async def create(self, document: NewDocument) -> dict[str, Any]:
        response = await self._send("POST", "/", json=asdict(document))
        if response.status_code == 409:
            raise DuplicateDocument()
        if response.status_code != 201:
            raise _unavailable(response)
        return response.json()

    async def forward(
        self, method: str, path: str, query: dict[str, str], body: bytes | None
    ) -> ProxiedResponse:
        headers = {"Content-Type": "application/json"} if body is not None else None
        response = await self._send(method, path, params=query, content=body, headers=headers)
        return ProxiedResponse(
            status_code=response.status_code,
            body=response.content,
            content_type=response.headers.get("content-type", ""),
        )

    async def _send(self, method: str, path: str, **options: Any) -> httpx.Response:
        try:
            return await self._client.request(method, f"{self._base_url}{path}", **options)
        except httpx.TransportError as error:
            logger.warning("No se pudo llegar a documents: %s", type(error).__name__)
            raise DocumentsUnavailable() from error


def _unavailable(response: httpx.Response) -> DocumentsUnavailable:
    logger.warning("documents respondió %s a %s", response.status_code, response.request.url.path)
    return DocumentsUnavailable()
