"""
File ingestion abstraction — THE extension point for supporting new file types.

The spec calls for "a clearly abstracted file handler with a single
well-documented extension point so adding new file types (text, markdown, DOCX)
later requires only adding a new parser class, not restructuring the pipeline."

This is that extension point. To support a new type:
    1. Subclass FileHandler.
    2. Set `extensions` (e.g. {".docx"}) and implement `extract()`.
    3. Register it in app/ingestion/handlers/registry.py (one line).
Nothing else in the pipeline changes — the chunker, embedder, Qdrant writer,
and routers all operate on the ParsedDocument this returns, independent of
source format.

A handler's ONE job: turn raw bytes into a ParsedDocument — an ordered list of
ParsedPage, each carrying its text and a 1-based page number. Page numbers are
not cosmetic: they become chunk provenance ("NICE NG28, p.42") shown on the
thinking-panel chunk cards, so handlers must populate them accurately.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class ParsedPage:
    """One page (or logical section) of a parsed document."""

    page_number: int  # 1-based
    text: str


@dataclass
class ParsedDocument:
    """The format-independent result every FileHandler produces."""

    pages: list[ParsedPage]

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class FileHandler(abc.ABC):
    """Interface for turning raw file bytes into a ParsedDocument."""

    #: File extensions this handler claims, lowercase incl. dot, e.g. {".pdf"}.
    extensions: set[str] = set()

    @abc.abstractmethod
    def extract(self, *, data: bytes, filename: str) -> ParsedDocument:
        """
        Parse raw bytes into pages of text. Implementations should:
          • preserve reading order,
          • assign accurate 1-based page numbers,
          • return text as-is (cleaning/normalisation happens in the chunker),
          • raise ValueError on unparseable/corrupt input.
        """
        raise NotImplementedError
