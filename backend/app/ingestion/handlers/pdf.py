from __future__ import annotations

import io

from app.ingestion.handlers.base import FileHandler, ParsedDocument, ParsedPage
from pypdf import PdfReader


class PdfFileHandler(FileHandler):
    extensions = {".pdf"}

    def extract(self, *, data: bytes, filename: str) -> ParsedDocument:
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise ValueError(f"Could not parse PDF {filename!r}: {exc}") from exc

        pages: list[ParsedPage] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append(ParsedPage(page_number=i, text=text))

        if not pages:
            raise ValueError(f"PDF {filename!r} has no pages")

        return ParsedDocument(pages=pages)
