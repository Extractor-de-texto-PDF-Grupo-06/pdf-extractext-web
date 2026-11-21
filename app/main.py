"""Punto de entrada: arma la aplicación FastAPI."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

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
