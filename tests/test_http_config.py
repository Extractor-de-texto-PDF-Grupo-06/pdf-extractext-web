"""Configuración centralizada: se lee de config con una caché de 5 s y, si falla, rige Settings."""

import httpx
import pytest

from app.application.entities import WebConfig
from app.infrastructure.http_config import HttpConfigSource

pytestmark = pytest.mark.anyio

FALLBACK = WebConfig(
    max_file_size_mb=10,
    extractor_timeout_seconds=30.0,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_seconds=30.0,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeConfigService:
    """Responde como config: ``GET /?prefix=web/`` con las entradas guardadas."""

    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.requests: list[httpx.Request] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("config apagado", request=request)
        entries = [{"key": key, "value": value, "index": 1} for key, value in self.values.items()]
        return httpx.Response(200, json={"entries": entries, "total": len(entries)})


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def config_service():
    return FakeConfigService(
        {
            "web/max_file_size_mb": "20",
            "web/extractor_timeout_seconds": "12.5",
            "web/circuit_breaker_failure_threshold": "3",
            "web/circuit_breaker_recovery_seconds": "60",
        }
    )


@pytest.fixture
async def source(config_service, clock):
    async with httpx.AsyncClient(transport=httpx.MockTransport(config_service)) as client:
        yield HttpConfigSource(client, "http://config:8000/", FALLBACK, clock=clock)


async def test_lee_los_valores_de_web_desde_config(source):
    assert await source.get() == WebConfig(
        max_file_size_mb=20,
        extractor_timeout_seconds=12.5,
        circuit_breaker_failure_threshold=3,
        circuit_breaker_recovery_seconds=60.0,
    )


async def test_pide_solo_las_claves_de_web_con_un_timeout_corto(source, config_service):
    await source.get()

    request = config_service.requests[0]
    assert str(request.url) == "http://config:8000/?prefix=web%2F"
    assert request.extensions["timeout"]["read"] == 2.0


async def test_una_clave_que_falta_toma_el_valor_de_respaldo(source, config_service):
    del config_service.values["web/max_file_size_mb"]

    assert (await source.get()).max_file_size_mb == 10


@pytest.mark.parametrize("value", ["diez", "0", "-5", ""])
async def test_un_valor_invalido_toma_el_valor_de_respaldo(source, config_service, value):
    config_service.values["web/circuit_breaker_failure_threshold"] = value

    config = await source.get()

    assert config.circuit_breaker_failure_threshold == 5
    assert config.max_file_size_mb == 20


async def test_con_config_caido_rigen_los_valores_de_respaldo(source, config_service):
    config_service.down = True

    assert await source.get() == FALLBACK


async def test_si_config_responde_un_error_rigen_los_valores_de_respaldo(clock):
    def failing(request):
        return httpx.Response(503, json={"detail": "Consul no responde"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(failing)) as client:
        source = HttpConfigSource(client, "http://config:8000", FALLBACK, clock=clock)

        assert await source.get() == FALLBACK


async def test_durante_5_segundos_usa_la_copia_guardada(source, config_service, clock):
    await source.get()
    config_service.values["web/max_file_size_mb"] = "50"
    clock.now += 4.9

    assert (await source.get()).max_file_size_mb == 20
    assert len(config_service.requests) == 1


async def test_pasados_5_segundos_toma_el_cambio_sin_reiniciar(source, config_service, clock):
    await source.get()
    config_service.values["web/max_file_size_mb"] = "50"
    clock.now += 5.0

    assert (await source.get()).max_file_size_mb == 50
    assert len(config_service.requests) == 2


async def test_con_config_caido_no_lo_consulta_en_cada_subida(source, config_service, clock):
    config_service.down = True
    await source.get()
    clock.now += 1.0

    await source.get()

    assert len(config_service.requests) == 1
