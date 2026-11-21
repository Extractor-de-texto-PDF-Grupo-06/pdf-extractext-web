# pdf-extractext-web

La **interfaz y el orquestador** de
[pdf-extractext](https://github.com/Extractor-de-texto-PDF-Grupo-06/pdf-extractext-orchestration).
El navegador solo habla con web: sirve la interfaz, coordina la subida de un PDF
(documents → extractor → documents) y reenvía el CRUD a documents (ADR 0004).

## Contrato

| Método y ruta | Qué hace |
|---|---|
| `GET /` | La interfaz |
| `POST /api/documents` | La subida (multipart, campo `file`). `201` · `400` · `409` · `413` · `415` · `422` · `502` · `503` con `Retry-After` si el circuito está abierto |
| `GET /api/documents`, `GET/PUT/DELETE /api/documents/{id}` | Reenvía a documents, con sus mismos códigos y cuerpos |
| `GET /api/health` | Estado de documents, extractor y config |
| `GET /health` | `200` mientras el proceso vive (para Docker y Traefik) |

Todo error responde `{"detail": "…"}`.

### La subida

1. Lee el PDF del multipart **en memoria**, como máximo `límite + 1` bytes: nunca se
   escribe a disco, ni siquiera de forma temporal.
2. Valida la extensión `.pdf`, el content-type y el tamaño.
3. Calcula el checksum SHA-256 y le pregunta a documents si ya existe (`409` sin extraer).
4. Llama al extractor detrás del circuit breaker. Un PDF inválido (`422`) no cuenta como
   falla; con 5 fallas seguidas el circuito se abre y la subida responde `503` sin llamarlo.
5. Le pide a documents que guarde. Si otra subida del mismo PDF llegó antes, `409`.

## Configuración

Por variables de entorno (ver `.env.example`). Los cuatro valores de la subida se pueden
cambiar **en caliente** desde config: web los pide con una caché de 5 segundos y, si config
no responde o una clave falta, usa los de sus variables de entorno.

| Clave en config | Variable de respaldo | Por defecto |
|---|---|---|
| `web/max_file_size_mb` | `MAX_FILE_SIZE_MB` | `10` |
| `web/extractor_timeout_seconds` | `EXTRACTOR_TIMEOUT_SECONDS` | `30` |
| `web/circuit_breaker_failure_threshold` | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` |
| `web/circuit_breaker_recovery_seconds` | `CIRCUIT_BREAKER_RECOVERY_SECONDS` | `30` |

Además: `DOCUMENTS_URL`, `EXTRACTOR_URL` (en el sistema, el entrypoint interno de Traefik,
ADR 0005), `CONFIG_URL`, los timeouts de los clientes y `PORT`.

## Desarrollo

```bash
uv sync --group dev
uv run pytest                   # sin red: los otros servicios son dobles o httpx.MockTransport
uv run python -m app.main       # levanta el servicio en PORT
docker build -t pdf-extractext-web:dev .
```

## Estructura

```
app/
├── presentation/     rutas, lector del multipart, errores e interfaz (static/)
├── application/      UploadDocument, circuit breaker, puertos y entidades; solo biblioteca estándar
├── infrastructure/   clientes HTTP de extractor, documents y config
├── core/             Settings
├── dependencies.py   arma las dependencias
└── main.py
tests/
├── test_architecture.py   la regla de dependencias entre capas
└── test_*.py
```

La interfaz y el circuit breaker vienen de documents con su historial
(`git log --follow app/application/circuit_breaker.py`).

La imagen es multi-stage: la final tiene solo el entorno virtual y el código, corre con el
usuario `10001` y declara un `HEALTHCHECK` contra `/health`. Funciona con el sistema de
archivos en solo lectura.
