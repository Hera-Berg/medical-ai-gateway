from __future__ import annotations

import pypdfium2 as pdfium
from app.ingestion.handlers.base import FileHandler, ParsedDocument, ParsedPage


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines)


class PdfFileHandler(FileHandler):
    extensions = {".pdf"}

    def extract(self, *, data: bytes, filename: str) -> ParsedDocument:
        try:
            pdf = pdfium.PdfDocument(data)
        except Exception as exc:
            raise ValueError(f"Could not parse PDF {filename!r}: {exc}") from exc

        pages: list[ParsedPage] = []
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                try:
                    textpage = page.get_textpage()
                    try:
                        raw = textpage.get_text_range() or ""
                    finally:
                        textpage.close()
                    text = _normalise(raw)
                except Exception:
                    text = ""
                finally:
                    page.close()
                pages.append(ParsedPage(page_number=i + 1, text=text))
        finally:
            pdf.close()

        if not pages:
            raise ValueError(f"PDF {filename!r} has no pages")

        return ParsedDocument(pages=pages)
