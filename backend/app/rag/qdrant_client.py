from __future__ import annotations

from app.config import get_settings
from qdrant_client import AsyncQdrantClient, models


class QdrantRAG:
    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncQdrantClient(url=s.qdrant_node_1_url)
        self._dim = s.embedding_dim

    @property
    def client(self) -> AsyncQdrantClient:
        return self._client

    async def ensure_collection(self, name: str) -> None:
        exists = await self._client.collection_exists(name)
        if exists:
            return
        await self._client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=self._dim,
                distance=models.Distance.COSINE,
            ),
            shard_number=2,
            replication_factor=2,
        )

    async def upsert_chunks(
        self,
        *,
        collection: str,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        points = [
            models.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in zip(point_ids, vectors, payloads)
        ]
        await self._client.upsert(collection_name=collection, points=points, wait=True)

    async def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        limit: int,
    ) -> list[models.ScoredPoint]:
        res = await self._client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        return res.points

    async def delete_document(self, *, collection: str, document_id: str) -> None:
        await self._client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def collection_stats(self, name: str) -> dict:
        info = await self._client.get_collection(name)
        return {
            "points_count": info.points_count,
            "status": str(info.status),
            "shard_number": info.config.params.shard_number,
            "replication_factor": info.config.params.replication_factor,
        }
