"""Adaptador del puerto ConfigSource: lee la configuración de web desde el servicio config.

Gana el primer nivel que exista (SPEC.md):
1. Consul, a través de config, con una caché de 5 segundos: un cambio vale sin reiniciar.
2. Los valores de respaldo (las variables de entorno de web), si config no responde o una
   clave falta o es inválida.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import fields, replace

import httpx

from app.application.entities import WebConfig

logger = logging.getLogger(__name__)

_PREFIX = "web/"


class HttpConfigSource:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        fallback: WebConfig,
        ttl_seconds: float = 5.0,
        timeout_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/"
        self._fallback = fallback
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._cached: WebConfig | None = None
        self._expires_at = 0.0

    async def get(self) -> WebConfig:
        if self._cached is None or self._clock() >= self._expires_at:
            # También se guarda el respaldo: con config caído no se lo espera en cada subida.
            self._cached = await self._fetch()
            self._expires_at = self._clock() + self._ttl
        return self._cached

    async def _fetch(self) -> WebConfig:
        try:
            response = await self._client.get(
                self._url, params={"prefix": _PREFIX}, timeout=self._timeout
            )
            response.raise_for_status()
            entries = response.json()["entries"]
            values = {entry["key"].removeprefix(_PREFIX): entry["value"] for entry in entries}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("config no respondió (%s): rigen las variables de entorno", error)
            return self._fallback
        return self._merge(values)

    def _merge(self, values: dict[str, str]) -> WebConfig:
        """Cada clave válida pisa su valor de respaldo; las demás lo conservan."""
        overrides = {}
        for field in fields(WebConfig):
            if field.name not in values:
                continue
            parsed = _positive(values[field.name], int if field.type is int else float)
            if parsed is None:
                logger.warning("Valor inválido para %s%s: se usa el de respaldo", _PREFIX, field.name)
            else:
                overrides[field.name] = parsed
        return replace(self._fallback, **overrides)


def _positive(value: str, kind: type) -> int | float | None:
    try:
        parsed = kind(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
