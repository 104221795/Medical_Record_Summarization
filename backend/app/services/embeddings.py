import hashlib
import math
import os
import re
from pathlib import Path
from abc import ABC, abstractmethod


TOKEN_RE = re.compile(r"[\w%./+-]+", re.UNICODE)


class EmbeddingProvider(ABC):
    name: str
    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedder for tests and non-clinical development only."""

    name = "hashing-development-only"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = TOKEN_RE.findall(text.casefold())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            return [value / norm for value in vector]
        return vector


class FastEmbedProvider(EmbeddingProvider):
    """ONNX Runtime embeddings suitable for local/private deployment."""

    name = "fastembed-onnx"

    def __init__(
        self,
        model_name: str,
        execution_provider: str = "CPUExecutionProvider",
        threads: int | None = None,
    ):
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "fastembed is not installed. Install requirements.txt "
                "for local ONNX embeddings."
            ) from exc
        self.model_name = model_name
        self.execution_provider = execution_provider
        self._model = TextEmbedding(
            model_name=model_name,
            providers=[execution_provider],
            threads=threads,
        )
        probe = next(iter(self._model.embed(["dimension probe"])))
        self.dimension = len(probe)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        inputs = [self._prefix(text, "passage") for text in texts]
        return [embedding.tolist() for embedding in self._model.embed(inputs)]

    def embed_query(self, text: str) -> list[float]:
        embedding = next(iter(self._model.embed([self._prefix(text, "query")])))
        return embedding.tolist()

    def _prefix(self, text: str, role: str) -> str:
        if "e5" in self.model_name.casefold():
            return f"{role}: {text}"
        return text


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    """SentenceTransformers embeddings for local evaluation and production-style retrieval."""

    name = "sentence-transformers"

    def __init__(
        self,
        model_name: str,
        *,
        cache_folder: str | Path | None = None,
        local_files_only: bool = True,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install requirements.txt "
                "or use embedding_provider=fastembed."
            ) from exc
        cache = str(cache_folder or os.environ.get("HF_HOME") or "D:/hf_cache")
        try:
            self._model = SentenceTransformer(
                model_name,
                cache_folder=cache,
                local_files_only=local_files_only,
            )
        except TypeError:
            if local_files_only:
                raise RuntimeError(
                    "Installed sentence-transformers does not support local_files_only; "
                    "cache the model first or use a fastembed backend."
                )
            self._model = SentenceTransformer(model_name, cache_folder=cache)
        self.model_name = model_name
        self.dimension = self._embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        inputs = [self._prefix(text, "passage") for text in texts]
        return self._model.encode(inputs, normalize_embeddings=True, show_progress_bar=False).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(
            [self._prefix(text, "query")],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0].tolist()

    def _embedding_dimension(self) -> int:
        if hasattr(self._model, "get_embedding_dimension"):
            return int(self._model.get_embedding_dimension() or 0)
        return int(self._model.get_sentence_embedding_dimension() or 0)

    def _prefix(self, text: str, role: str) -> str:
        normalized = self.model_name.casefold()
        if "e5" in normalized:
            return f"{role}: {text}"
        if "bge" in normalized and role == "query":
            return f"Represent this sentence for searching relevant passages: {text}"
        return text
