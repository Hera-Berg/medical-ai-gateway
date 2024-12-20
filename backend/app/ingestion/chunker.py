from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.ingestion.handlers.base import ParsedDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkRecord:
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
    token_count: int | None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Chunker:
    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        s = get_settings()
        self.chunk_size = chunk_size or s.chunk_size
        self.chunk_overlap = chunk_overlap or s.chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
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
