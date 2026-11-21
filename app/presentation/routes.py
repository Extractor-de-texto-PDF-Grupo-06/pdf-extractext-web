"""Rutas de web. Es lo único que el navegador conoce del sistema."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.presentation.state import Services, get_services
from app.presentation.upload_reader import read_pdf_upload

router = APIRouter()

ServicesDep = Annotated[Services, Depends(get_services)]


@router.get("/health")
async def health() -> dict:
    """Vida del proceso, para Docker y Traefik. No consulta a los otros servicios."""
    return {"status": "ok"}


@router.post("/api/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(request: Request, services: ServicesDep) -> JSONResponse:
    """Recibe el PDF en el campo ``file`` (multipart) y lo guarda como documento."""
    pdf = await read_pdf_upload(request, await services.upload.max_file_bytes())
    created = await services.upload.execute(pdf)
    return JSONResponse(created, status_code=status.HTTP_201_CREATED)
