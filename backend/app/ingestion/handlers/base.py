from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class FileHandler(abc.ABC):
    extensions: set[str] = set()

    @abc.abstractmethod
    def extract(self, *, data: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError
