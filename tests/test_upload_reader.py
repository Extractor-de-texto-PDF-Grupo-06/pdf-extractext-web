"""Lector del multipart, con el cuerpo llegando en partes como lo entrega uvicorn."""

import pytest
from starlette.requests import Request

from app.presentation.upload_reader import read_pdf_upload

pytestmark = pytest.mark.anyio

BOUNDARY = "limite"


def multipart(data: bytes, filename: str = "informe.pdf") -> bytes:
    return (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode() + data + f"\r\n--{BOUNDARY}--\r\n".encode()


def request_in_chunks(body: bytes, chunk_size: int) -> Request:
    chunks = [body[i:i + chunk_size] for i in range(0, len(body), chunk_size)]

    async def receive():
        chunk = chunks.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

    headers = [(b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode())]
    return Request({"type": "http", "method": "POST", "headers": headers}, receive)


async def test_arma_el_pdf_aunque_llegue_en_muchas_partes():
    pdf = await read_pdf_upload(request_in_chunks(multipart(b"%PDF-1.4 " + b"x" * 5000), 64), 10_000)

    assert pdf.filename == "informe.pdf"
    assert pdf.content_type == "application/pdf"
    assert pdf.data == b"%PDF-1.4 " + b"x" * 5000


async def test_si_supera_el_limite_deja_de_leer_y_devuelve_un_byte_de_mas():
    received = request_in_chunks(multipart(b"x" * 100_000), 1024)

    pdf = await read_pdf_upload(received, 10_000)

    assert len(pdf.data) == 10_001


async def test_toma_solo_el_nombre_aunque_el_navegador_mande_la_ruta():
    body = multipart(b"%PDF", filename="C:\\Usuarios\\ana\\informe.pdf")

    pdf = await read_pdf_upload(request_in_chunks(body, 64), 10_000)

    assert pdf.filename == "informe.pdf"
