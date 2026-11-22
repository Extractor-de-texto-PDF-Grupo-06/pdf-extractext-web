"""Lectura de los imports de un paquete para verificar la regla de dependencias entre capas."""

import ast
import sys
from pathlib import Path


def imported_modules(package: Path) -> set[str]:
    """Devuelve el nombre completo de cada módulo que importa algún archivo del paquete."""
    modules: set[str] = set()
    for source in package.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module)
    return modules


def non_stdlib_imports(package: Path, own_package: str) -> set[str]:
    """Imports que no son de la biblioteca estándar ni del propio paquete."""
    return {
        module
        for module in imported_modules(package)
        if module.split(".")[0] not in sys.stdlib_module_names
        and not _belongs_to(module, own_package)
    }


def imports_of(package: Path, forbidden: str) -> set[str]:
    """Imports del paquete que apuntan a ``forbidden`` o a sus submódulos."""
    return {module for module in imported_modules(package) if _belongs_to(module, forbidden)}


def _belongs_to(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")
