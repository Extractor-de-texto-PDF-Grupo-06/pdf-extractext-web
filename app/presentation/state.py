"""Lo que la aplicación arma al arrancar y las rutas usan."""

from dataclasses import dataclass

from fastapi import Request

from app.application.ports import DependencyHealth, DocumentsProxy
from app.application.use_cases import UploadDocument


@dataclass(frozen=True)
class Services:
    upload: UploadDocument
    documents: DocumentsProxy
    health: DependencyHealth


def get_services(request: Request) -> Services:
    return request.app.state.services
