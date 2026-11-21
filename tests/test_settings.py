"""Settings: toda la configuración del proceso entra por variables de entorno (factor III)."""

from app.application.entities import WebConfig
from app.core.settings import Settings
from app.dependencies import fallback_config

NAMES = (
    "DOCUMENTS_URL", "EXTRACTOR_URL", "CONFIG_URL", "MAX_FILE_SIZE_MB", "EXTRACTOR_TIMEOUT_SECONDS",
    "CIRCUIT_BREAKER_FAILURE_THRESHOLD", "CIRCUIT_BREAKER_RECOVERY_SECONDS", "CONFIG_CACHE_SECONDS",
    "CONFIG_TIMEOUT_SECONDS", "DOCUMENTS_TIMEOUT_SECONDS", "PORT",
)


def test_valores_por_defecto_para_desarrollo_local(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.documents_url == "http://localhost:8001"
    assert settings.extractor_url == "http://localhost:8080"
    assert settings.config_url == "http://localhost:8003"
    assert settings.max_file_size_mb == 10
    assert settings.extractor_timeout_seconds == 30.0
    assert settings.circuit_breaker_failure_threshold == 5
    assert settings.circuit_breaker_recovery_seconds == 30.0
    assert settings.config_cache_seconds == 5.0
    assert settings.config_timeout_seconds == 2.0
    assert settings.documents_timeout_seconds == 10.0
    assert settings.port == 8000


def test_las_variables_de_entorno_pisan_los_valores_por_defecto(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_URL", "http://traefik:8081/extractor")
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "25")

    settings = Settings(_env_file=None)

    assert settings.extractor_url == "http://traefik:8081/extractor"
    assert settings.max_file_size_mb == 25


def test_el_respaldo_de_la_configuracion_centralizada_sale_de_settings(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "7")

    assert fallback_config(Settings(_env_file=None)) == WebConfig(
        max_file_size_mb=10,
        extractor_timeout_seconds=30.0,
        circuit_breaker_failure_threshold=7,
        circuit_breaker_recovery_seconds=30.0,
    )
