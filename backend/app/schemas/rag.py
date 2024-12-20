from __future__ import annotations

import uuid
from datetime import date, datetime

from app.db.models import CorpusType
from pydantic import BaseModel, ConfigDict


class CollectionCreate(BaseModel):
    name: str
    corpus_type: CorpusType
    description: str | None = None


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    corpus_type: CorpusType
    qdrant_collection: str
    description: str | None
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collection_id: uuid.UUID
    filename: str
    storage_backend: str
    source_version: str | None
    published_date: date | None
    source_url: str | None
    chunk_count: int
    uploaded_at: datetime
