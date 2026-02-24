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

    async def cluster_info(self) -> dict:
        import httpx
        from app.config import get_settings

        url = get_settings().qdrant_node_1_url.rstrip("/") + "/cluster"
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(url)
                r.raise_for_status()
                result = r.json().get("result", {})
        except Exception:
            return {}
        peers = result.get("peers", {})
        return {
            "status": result.get("status"),
            "peer_id": result.get("peer_id"),
            "peer_count": len(peers),
            "peers": [
                {"peer_id": pid, "uri": pinfo.get("uri")}
                for pid, pinfo in peers.items()
            ],
        }

    async def collection_shards(self, name: str) -> dict:
        import httpx
        from app.config import get_settings

        url = (
            get_settings().qdrant_node_1_url.rstrip("/")
            + f"/collections/{name}/cluster"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(url)
                r.raise_for_status()
                result = r.json().get("result", {})
        except Exception:
            return {}
        local = result.get("local_shards", [])
        remote = result.get("remote_shards", [])
        return {
            "peer_id": result.get("peer_id"),
            "shard_count": result.get("shard_count"),
            "local_shards": [
                {
                    "shard_id": s.get("shard_id"),
                    "state": s.get("state"),
                    "points": s.get("points"),
                }
                for s in local
            ],
            "remote_shards": [
                {
                    "shard_id": s.get("shard_id"),
                    "peer_id": s.get("peer_id"),
                    "state": s.get("state"),
                }
                for s in remote
            ],
        }

    async def get_vectors_by_point_ids(
        self, *, collection: str, point_ids: list[str]
    ) -> dict[str, list[float]]:
        if not point_ids:
            return {}
        records = await self._client.retrieve(
            collection_name=collection,
            ids=point_ids,
            with_vectors=True,
            with_payload=False,
        )
        out: dict[str, list[float]] = {}
        for r in records:
            vec = r.vector
            if isinstance(vec, dict):
                vec = next(iter(vec.values()))
            if vec is not None:
                out[str(r.id)] = list(vec)
        return out

    async def scroll_all_points(
        self, *, collection: str, with_vectors: bool = True, limit: int = 10000
    ) -> list[dict]:
        results: list[dict] = []
        offset = None
        while len(results) < limit:
            batch, offset = await self._client.scroll(
                collection_name=collection,
                with_vectors=with_vectors,
                with_payload=True,
                limit=min(256, limit - len(results)),
                offset=offset,
            )
            for r in batch:
                vec = r.vector
                if isinstance(vec, dict):
                    vec = next(iter(vec.values()))
                results.append(
                    {
                        "id": str(r.id),
                        "vector": list(vec) if vec else None,
                        "payload": r.payload or {},
                    }
                )
            if offset is None or not batch:
                break
        return results
