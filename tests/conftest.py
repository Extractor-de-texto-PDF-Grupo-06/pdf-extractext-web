"""Fixtures compartidas por los tests."""

import pytest


@pytest.fixture
def anyio_backend():
    """Los tests asíncronos (marcados con anyio) corren sobre asyncio, como uvicorn."""
    return "asyncio"
