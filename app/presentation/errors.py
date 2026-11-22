"""Traduce los errores de los casos de uso a respuestas HTTP con la forma {"detail": "…"}."""

import math

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.application.circuit_breaker import CircuitOpenError
from app.application.errors import (
    DocumentsUnavailable,
    DuplicateDocument,
    ExtractorUnavailable,
    FileTooLarge,
    InvalidPdf,
    NotAPdfName,
    UnsupportedMediaType,
    UploadError,
)
from app.presentation.upload_reader import MalformedUpload

_STATUS_BY_ERROR: dict[type[UploadError], int] = {
    NotAPdfName: status.HTTP_400_BAD_REQUEST,
    UnsupportedMediaType: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    FileTooLarge: status.HTTP_413_CONTENT_TOO_LARGE,
    DuplicateDocument: status.HTTP_409_CONFLICT,
    InvalidPdf: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ExtractorUnavailable: status.HTTP_502_BAD_GATEWAY,
    DocumentsUnavailable: status.HTTP_502_BAD_GATEWAY,
}


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(UploadError, _upload_error)
    app.add_exception_handler(CircuitOpenError, _circuit_open)
    app.add_exception_handler(MalformedUpload, _malformed_upload)
    app.add_exception_handler(RequestValidationError, _validation_error)


async def _upload_error(request: Request, exc: UploadError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=_STATUS_BY_ERROR[type(exc)])


async def _circuit_open(request: Request, exc: CircuitOpenError) -> JSONResponse:
    """El cliente sabe cuándo volver a intentar; al menos un segundo, nunca cero."""
    return JSONResponse(
        {"detail": "El servicio de extracción falló varias veces seguidas. Intentá más tarde."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Retry-After": str(max(1, math.ceil(exc.retry_after)))},
    )


async def _malformed_upload(request: Request, exc: MalformedUpload) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI devuelve una lista de errores; el contrato pide un solo texto."""
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
        for error in exc.errors()
    )
    return JSONResponse(
        {"detail": f"Pedido inválido: {problems}"},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
