from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient, models

from ..schemas import EvidenceChunk


class QdrantVectorStore:
    """Qdrant-backed evidence store with mandatory tenant/patient filtering."""

    def __init__(
        self,
        collection_name: str,
        vector_size: int,
        *,
        path: Path | None = None,
        url: str | None = None,
        api_key: str | None = None,
    ):
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        elif path:
            path.mkdir(parents=True, exist_ok=True)
            try:
                self.client = QdrantClient(path=str(path))
            except RuntimeError as exc:
                if "already accessed by another instance" in str(exc):
                    raise RuntimeError(
                        "Local persistent Qdrant storage is single-process only. "
                        "Unset RAG_QDRANT_PATH for in-memory development with --reload, "
                        "or configure RAG_QDRANT_URL for concurrent workers."
                    ) from exc
                raise
        else:
            self.client = QdrantClient(":memory:")
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    def upsert(
        self,
        tenant_id: str,
        chunks: list[EvidenceChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one vector.")
        points = [
            models.PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload=self._to_payload(tenant_id, chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def delete_patient(self, tenant_id: str, patient_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=self._scope_filter(tenant_id, patient_id)
            ),
        )

    def search(
        self,
        tenant_id: str,
        patient_id: str,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None = None,
    ) -> list[EvidenceChunk]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=self._scope_filter(tenant_id, patient_id),
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            self._from_payload(point.payload or {}, float(point.score))
            for point in response.points
        ]

    def count_patient(self, tenant_id: str, patient_id: str) -> int:
        result = self.client.count(
            collection_name=self.collection_name,
            count_filter=self._scope_filter(tenant_id, patient_id),
            exact=True,
        )
        return result.count

    @staticmethod
    def _scope_filter(tenant_id: str, patient_id: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=tenant_id),
                ),
                models.FieldCondition(
                    key="patient_id",
                    match=models.MatchValue(value=patient_id),
                ),
            ]
        )

    @staticmethod
    def _to_payload(tenant_id: str, chunk: EvidenceChunk) -> dict:
        return {
            "chunk_id": chunk.chunk_id,
            "tenant_id": tenant_id,
            "patient_id": chunk.patient_id,
            "document_id": chunk.document_id,
            "document_type": chunk.document_type,
            "title": chunk.title,
            "encounter_id": chunk.encounter_id,
            "authored_at": chunk.authored_at.isoformat() if chunk.authored_at else None,
            "section": chunk.section,
            "text": chunk.text,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }

    @staticmethod
    def _from_payload(payload: dict, score: float) -> EvidenceChunk:
        authored_at = payload.get("authored_at")
        return EvidenceChunk(
            chunk_id=str(payload["chunk_id"]),
            patient_id=str(payload["patient_id"]),
            document_id=str(payload["document_id"]),
            document_type=str(payload["document_type"]),
            title=payload.get("title"),
            encounter_id=payload.get("encounter_id"),
            authored_at=datetime.fromisoformat(authored_at) if authored_at else None,
            section=str(payload["section"]),
            text=str(payload["text"]),
            char_start=int(payload["char_start"]),
            char_end=int(payload["char_end"]),
            score=score,
        )
