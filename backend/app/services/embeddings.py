import hashlib
import math
import re
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
                "fastembed is not installed. Install requirements-rag-onnx.txt "
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
