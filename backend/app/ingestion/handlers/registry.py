"""
File handler registry — maps a file extension to its FileHandler.

Adding a new file type is one register call here plus the handler class.
The ingestion pipeline calls get_handler_for(filename) and never needs to know
which concrete handler runs.
"""
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
            f"No file handler for extension {ext!r}. "
            f"Supported: {sorted(_HANDLERS)}"
        )
    return handler


def supported_extensions() -> list[str]:
    return sorted(_HANDLERS)


# ── Registration (extension point) ──────────────────────────────────────────
register_handler(PdfFileHandler())
# register_handler(DocxFileHandler())   # future: just add the class + this line
# register_handler(MarkdownFileHandler())
