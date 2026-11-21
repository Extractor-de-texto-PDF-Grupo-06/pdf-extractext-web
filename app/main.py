"""Punto de entrada: arma la aplicación FastAPI."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.core.settings import Settings
from app.dependencies import http_services
from app.presentation.errors import add_error_handlers
from app.presentation.routes import router
from app.presentation.state import Services

ServicesFactory = Callable[[], AbstractAsyncContextManager[Services]]


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
    return app


settings = Settings()
app = create_app(lambda: http_services(settings))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
