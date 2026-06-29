"""
PdfFileHandler — PDF text extraction via pypdfium2 (Apache/BSD licensed, built on
Google's PDFium, the engine in Chrome).

We switched from pypdf to pypdfium2 because pypdf mis-read the character-spacing
encoding in some clinical-guideline PDFs, inserting spurious spaces mid-word
("pr escrip tive", "E videnc e-Based"). That corrupts both the embeddings and the
citation text shown on chunk cards — unacceptable for a tool whose product IS the
evidence text. pypdfium2 handles these encodings correctly.

This swap touched ONLY this file — the FileHandler contract (bytes ->
ParsedDocument) is unchanged, so the chunker, embedder, Qdrant writer, and
routers are all untouched. That's the payoff of the extension-point design.

(Licensing note: pypdfium2 is Apache/BSD — permissive, no copyleft. PyMuPDF was
the other obvious option but is AGPL, which would impose copyleft obligations.)
"""
from __future__ import annotations

import pypdfium2 as pdfium

from app.ingestion.handlers.base import FileHandler, ParsedDocument, ParsedPage


def _normalise(text: str) -> str:
    # pypdfium2 emits \r\n; normalise to \n and trim trailing whitespace per line
    # so chunk text and provenance display cleanly.
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
                    # one bad page shouldn't sink the whole document
                    text = ""
                finally:
                    page.close()
                pages.append(ParsedPage(page_number=i + 1, text=text))
        finally:
            pdf.close()

        if not pages:
            raise ValueError(f"PDF {filename!r} has no pages")

        return ParsedDocument(pages=pages)
