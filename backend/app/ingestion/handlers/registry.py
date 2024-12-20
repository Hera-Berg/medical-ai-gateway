from __future__ import annotations

import os

from app.ingestion.handlers.base import FileHandler
from app.ingestion.handlers.pdf import PdfFileHandler

_HANDLERS: dict[str, FileHandler] = {}


def register_handler(handler: FileHandler) -> None:
    for ext in handler.extensions:
        _HANDLERS[ext.lower()] = handler


def get_handler_for(filename: str) -> FileHandler:
    ext = os.path.splitext(filename)[1].lower()
    handler = _HANDLERS.get(ext)
    if handler is None:
        raise ValueError(
            f"No file handler for extension {ext!r}. " f"Supported: {sorted(_HANDLERS)}"
        )
    return handler


def supported_extensions() -> list[str]:
    return sorted(_HANDLERS)


register_handler(PdfFileHandler())
