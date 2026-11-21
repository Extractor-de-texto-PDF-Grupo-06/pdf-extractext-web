"""Adaptador del puerto DependencyHealth: consulta el /health de cada servicio a la vez."""

import asyncio

import httpx

_TIMEOUT_SECONDS = 2.0


class HttpHealth:
    def __init__(self, client: httpx.AsyncClient, base_urls: dict[str, str]) -> None:
        self._client = client
        self._urls = {name: f"{url.rstrip('/')}/health" for name, url in base_urls.items()}

    async def check(self) -> dict[str, bool]:
        answers = await asyncio.gather(*(self._is_up(url) for url in self._urls.values()))
        return dict(zip(self._urls, answers))

    async def _is_up(self, url: str) -> bool:
        try:
            response = await self._client.get(url, timeout=_TIMEOUT_SECONDS)
        except httpx.TransportError:
            return False
        return response.status_code == 200
