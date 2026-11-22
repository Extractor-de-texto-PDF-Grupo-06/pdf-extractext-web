"""Punto de entrada: arma la aplicación FastAPI."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.settings import Settings
from app.dependencies import http_services
from app.presentation.errors import add_error_handlers
from app.presentation.routes import router
from app.presentation.state import Services

ServicesFactory = Callable[[], AbstractAsyncContextManager[Services]]

STATIC_DIR = Path(__file__).resolve().parent / "presentation" / "static"


def create_app(services_factory: ServicesFactory) -> FastAPI:
    """``services_factory`` abre los clientes al arrancar y los cierra al apagarse (factor IX)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services_factory() as services:
            app.state.services = services
            yield

    app = FastAPI(title="pdf-extractext-web", lifespan=lifespan)
    app.include_router(router)
    add_error_handlers(app)
    # Al final: las rutas de arriba ganan, y todo lo demás es la interfaz (GET / es index.html).
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="interfaz")
    return app


settings = Settings()
app = create_app(lambda: http_services(settings))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
