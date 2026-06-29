"""
Chunker — turns a ParsedDocument into ordered Chunk records ready for embedding.

Design:
  • We chunk PER PAGE, then concatenate, so every chunk knows its source page
    (needed for provenance: "NICE NG28, p.42"). A chunk never spans two pages —
    a small loss of cross-page context in exchange for accurate citations, which
    matters more for a clinical-comparison tool than squeezing the last bit of
    recall. (Documented trade-off; revisit if recall suffers.)
  • RecursiveCharacterTextSplitter (LangChain, per the spec's "LangChain for
    orchestration") splits on paragraph/sentence boundaries before falling back
    to hard character cuts, so chunks tend to break at natural boundaries.
  • chunk_size / overlap are config so they're tunable without code changes.
  • We attach chunk_index (global order within the document), page_number, and a
    cheap token estimate. `section` is left None for now — pypdf doesn't give us
    heading structure reliably; a later handler (or a heading-detection pass)
    can populate it. The schema column already exists.

Output is a list of ChunkRecord dataclasses; the router persists these to
Postgres (chunks table) and hands their text to the embedder.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.ingestion.handlers.base import ParsedDocument


@dataclass
class ChunkRecord:
    chunk_index: int          # 0-based, order within the document
    text: str
    page_number: int | None
    section: str | None
    token_count: int | None


def _estimate_tokens(text: str) -> int:
    # Cheap heuristic (~4 chars/token for English). Good enough for the UI's
    # per-chunk token display and rough cost math; not used for billing.
    return max(1, len(text) // 4)


class Chunker:
    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        s = get_settings()
        self.chunk_size = chunk_size or s.chunk_size
        self.chunk_overlap = chunk_overlap or s.chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],  # natural -> hard fallback
            length_function=len,
        )

    def chunk(self, doc: ParsedDocument) -> list[ChunkRecord]:
        records: list[ChunkRecord] = []
        idx = 0
        for page in doc.pages:
            text = page.text.strip()
            if not text:
                continue
            for piece in self._splitter.split_text(text):
                piece = piece.strip()
                if not piece:
                    continue
                records.append(
                    ChunkRecord(
                        chunk_index=idx,
                        text=piece,
                        page_number=page.page_number,
                        section=None,
                        token_count=_estimate_tokens(piece),
                    )
                )
                idx += 1
        return records
