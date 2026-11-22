"""Errores de la subida. El mensaje es el que recibe el cliente en ``detail``."""


class UploadError(Exception):
    """Base de los errores de la subida."""


class NotAPdfName(UploadError):
    def __init__(self) -> None:
        super().__init__("El archivo debe tener extensión .pdf.")


class UnsupportedMediaType(UploadError):
    def __init__(self) -> None:
        super().__init__("El content-type declarado debe ser application/pdf.")


class FileTooLarge(UploadError):
    def __init__(self, max_file_size_mb: int | None = None) -> None:
        limit = f" de {max_file_size_mb} MB" if max_file_size_mb is not None else ""
        super().__init__(f"El archivo supera el tamaño máximo{limit}.")


class DuplicateDocument(UploadError):
    def __init__(self) -> None:
        super().__init__("Ese PDF ya está guardado.")


class InvalidPdf(UploadError):
    """El extractor rechazó el PDF: está corrupto, tiene contraseña o no es un PDF."""


class ExtractorUnavailable(UploadError):
    def __init__(self) -> None:
        super().__init__("El servicio de extracción no respondió. Intentá de nuevo en unos segundos.")


class DocumentsUnavailable(UploadError):
    def __init__(self) -> None:
        super().__init__("El servicio de documentos no respondió. Intentá de nuevo en unos segundos.")
