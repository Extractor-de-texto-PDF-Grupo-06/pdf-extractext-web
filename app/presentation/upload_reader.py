"""Lee el PDF de un pedido multipart/form-data en memoria, sin pasar por disco.

``UploadFile`` de Starlette guarda en un archivo temporal todo lo que pasa de 1 MB, y la
especificación prohíbe escribir el PDF a disco (además, los contenedores corren con el
sistema de archivos en solo lectura). Por eso se procesa el multipart a medida que llega
y se deja de leer apenas se supera el límite.
"""

from fastapi import Request
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from app.application.entities import PdfFile

_FIELD = b"file"


class MalformedUpload(Exception):
    """El pedido no trae el PDF como lo pide el contrato."""


async def read_pdf_upload(request: Request, max_bytes: int) -> PdfFile:
    """El primer archivo del campo ``file``. Lee como máximo ``max_bytes + 1`` bytes de él:
    si llegan todos, el archivo supera el límite y lo rechaza quien valida."""
    media_type, options = parse_options_header(request.headers.get("content-type", ""))
    if media_type != b"multipart/form-data" or b"boundary" not in options:
        raise MalformedUpload("El PDF tiene que llegar como multipart/form-data en el campo 'file'.")

    part = _FilePart(limit=max_bytes + 1)
    parser = MultipartParser(options[b"boundary"], part.callbacks())
    try:
        async for chunk in request.stream():
            parser.write(chunk)
            if part.full:
                break
        else:
            parser.finalize()
    except MultipartParseError as error:
        raise MalformedUpload("El pedido multipart está mal formado.") from error

    if not part.found:
        raise MalformedUpload("Falta el archivo PDF en el campo 'file'.")
    return PdfFile(filename=part.filename, content_type=part.content_type, data=bytes(part.data))


class _FilePart:
    """Junta en memoria los bytes de la primera parte ``file`` y descarta el resto."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._headers: dict[bytes, bytes] = {}
        self._field = b""
        self._value = b""
        self._capturing = False
        self.found = False
        self.filename = ""
        self.content_type = ""
        self.data = bytearray()

    @property
    def full(self) -> bool:
        return len(self.data) >= self._limit

    def callbacks(self) -> dict:
        return {
            "on_part_begin": self._on_part_begin,
            "on_header_field": self._on_header_field,
            "on_header_value": self._on_header_value,
            "on_header_end": self._on_header_end,
            "on_headers_finished": self._on_headers_finished,
            "on_part_data": self._on_part_data,
            "on_part_end": self._on_part_end,
        }

    def _on_part_begin(self) -> None:
        self._headers = {}

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._field += data[start:end]

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._value += data[start:end]

    def _on_header_end(self) -> None:
        self._headers[self._field.lower()] = self._value
        self._field = b""
        self._value = b""

    def _on_headers_finished(self) -> None:
        _, disposition = parse_options_header(self._headers.get(b"content-disposition", b""))
        if self.found or disposition.get(b"name") != _FIELD or b"filename" not in disposition:
            return
        self._capturing = True
        self.filename = _basename(disposition[b"filename"].decode("utf-8", errors="replace"))
        self.content_type = self._headers.get(b"content-type", b"").decode("latin-1").strip()

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._capturing:
            self.data += data[start:min(end, start + self._limit - len(self.data))]

    def _on_part_end(self) -> None:
        if self._capturing:
            self._capturing = False
            self.found = True


def _basename(filename: str) -> str:
    """Algunos navegadores mandan la ruta completa del archivo; solo interesa el nombre."""
    return filename.replace("\\", "/").rsplit("/", 1)[-1]
