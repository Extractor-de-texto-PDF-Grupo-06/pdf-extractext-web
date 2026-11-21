"""Los casos de uso que la aplicación arma al arrancar y las rutas usan."""

from dataclasses import dataclass

from fastapi import Request

from app.application.use_cases import UploadDocument


@dataclass(frozen=True)
class Services:
    upload: UploadDocument


def get_services(request: Request) -> Services:
    return request.app.state.services
