"""Rutas de web. Es lo único que el navegador conoce del sistema."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.application.entities import ProxiedResponse
from app.presentation.state import Services, get_services
from app.presentation.upload_reader import read_pdf_upload

router = APIRouter()

ServicesDep = Annotated[Services, Depends(get_services)]


@router.get("/health")
async def health() -> dict:
    """Vida del proceso, para Docker y Traefik. No consulta a los otros servicios."""
    return {"status": "ok"}


@router.get("/api/health")
async def dependencies_health(services: ServicesDep) -> dict:
    """El estado de web y de cada servicio del que depende."""
    answers = await services.health.check()
    return {
        "status": "ok" if all(answers.values()) else "degraded",
        "services": {name: "ok" if up else "down" for name, up in answers.items()},
    }


@router.post("/api/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(request: Request, services: ServicesDep) -> JSONResponse:
    """Recibe el PDF en el campo ``file`` (multipart) y lo guarda como documento."""
    pdf = await read_pdf_upload(request, await services.upload.max_file_bytes())
    created = await services.upload.execute(pdf)
    return JSONResponse(created, status_code=status.HTTP_201_CREATED)


# El CRUD se reenvía a documents tal cual: códigos, errores y cuerpos son los de su contrato.


@router.get("/api/documents")
async def list_documents(request: Request, services: ServicesDep) -> Response:
    return await _forward(services, "GET", "/", dict(request.query_params))


@router.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, services: ServicesDep) -> Response:
    return await _forward(services, "GET", _document_path(doc_id))


@router.put("/api/documents/{doc_id}")
async def update_document(doc_id: str, request: Request, services: ServicesDep) -> Response:
    return await _forward(services, "PUT", _document_path(doc_id), body=await request.body())


@router.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str, services: ServicesDep) -> Response:
    return await _forward(services, "DELETE", _document_path(doc_id))


def _document_path(doc_id: str) -> str:
    return f"/{quote(doc_id, safe='')}"


async def _forward(
    services: Services,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: bytes | None = None,
) -> Response:
    answer: ProxiedResponse = await services.documents.forward(method, path, query or {}, body)
    if answer.status_code == status.HTTP_204_NO_CONTENT:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(answer.body, status_code=answer.status_code, media_type=answer.content_type)
