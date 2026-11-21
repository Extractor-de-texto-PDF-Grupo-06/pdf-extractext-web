"""Arma las dependencias: el único lugar que conoce todas las capas a la vez."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.application.circuit_breaker import CircuitBreaker
from app.application.entities import WebConfig
from app.application.use_cases import UploadDocument
from app.core.settings import Settings
from app.infrastructure.http_config import HttpConfigSource
from app.infrastructure.http_documents import HttpDocuments
from app.infrastructure.http_extractor import HttpExtractor
from app.presentation.state import Services


def fallback_config(settings: Settings) -> WebConfig:
    """Los valores de las variables de entorno, que rigen si config no responde."""
    return WebConfig(
        max_file_size_mb=settings.max_file_size_mb,
        extractor_timeout_seconds=settings.extractor_timeout_seconds,
        circuit_breaker_failure_threshold=settings.circuit_breaker_failure_threshold,
        circuit_breaker_recovery_seconds=settings.circuit_breaker_recovery_seconds,
    )


@asynccontextmanager
async def http_services(settings: Settings) -> AsyncIterator[Services]:
    """Los casos de uso sobre los otros servicios. Cierra las conexiones al salir."""
    # trust_env=False: los proxies del entorno no se aplican a la red interna.
    async with httpx.AsyncClient(
        timeout=settings.documents_timeout_seconds, trust_env=False
    ) as client:
        fallback = fallback_config(settings)
        config = HttpConfigSource(
            client,
            settings.config_url,
            fallback,
            ttl_seconds=settings.config_cache_seconds,
            timeout_seconds=settings.config_timeout_seconds,
        )
        breaker = CircuitBreaker(
            "extractor",
            failure_threshold=fallback.circuit_breaker_failure_threshold,
            recovery_timeout=fallback.circuit_breaker_recovery_seconds,
        )
        upload = UploadDocument(
            HttpExtractor(client, settings.extractor_url),
            HttpDocuments(client, settings.documents_url),
            config,
            breaker,
        )
        yield Services(upload=upload)
