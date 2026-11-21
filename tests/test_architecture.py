"""Regla de dependencias: application solo conoce la biblioteca estándar y nadie depende de presentation."""

from pathlib import Path

from tests.architecture import imports_of, non_stdlib_imports

APP = Path(__file__).resolve().parent.parent / "app"


def test_application_solo_usa_la_biblioteca_estandar():
    assert (APP / "application").is_dir()
    assert non_stdlib_imports(APP / "application", own_package="app.application") == set()


def test_application_no_conoce_las_otras_capas():
    for layer in ("app.presentation", "app.infrastructure", "app.core", "app.dependencies"):
        assert imports_of(APP / "application", layer) == set()


def test_presentation_no_conoce_la_infraestructura():
    assert imports_of(APP / "presentation", "app.infrastructure") == set()


def test_infrastructure_no_conoce_la_presentacion():
    assert imports_of(APP / "infrastructure", "app.presentation") == set()


def test_la_regla_detecta_una_libreria_externa(tmp_path):
    (tmp_path / "use_case.py").write_text("import hashlib\nimport httpx\n", encoding="utf-8")

    assert non_stdlib_imports(tmp_path, own_package="app.application") == {"httpx"}


def test_la_regla_detecta_un_import_de_otra_capa(tmp_path):
    (tmp_path / "use_case.py").write_text(
        "from app.infrastructure.http_extractor import HttpExtractor\n", encoding="utf-8"
    )

    assert imports_of(tmp_path, "app.infrastructure") == {"app.infrastructure.http_extractor"}
