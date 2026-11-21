"""Única fuente de configuración del proceso: variables de entorno (factor III).

Ningún otro módulo lee os.environ. Los cuatro valores de la subida también se pueden
cambiar en caliente desde config; acá están los de respaldo.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Servicios de los que depende (factor IV: se reemplazan cambiando una URL) ──
    documents_url: str = "http://localhost:8001"
    # En el compose, el entrypoint interno de Traefik, que balancea las réplicas (ADR 0005).
    extractor_url: str = "http://localhost:8080"
    config_url: str = "http://localhost:8003"

    # ── Respaldo de la configuración centralizada (claves web/…) ──
    max_file_size_mb: int = 10
    extractor_timeout_seconds: float = 30.0
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0

    # ── Clientes HTTP ──
    config_cache_seconds: float = 5.0
    config_timeout_seconds: float = 2.0
    documents_timeout_seconds: float = 10.0

    # Puerto HTTP del servicio (factor VII).
    port: int = 8000
