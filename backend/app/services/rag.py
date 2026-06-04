from time import perf_counter

from ..config import Settings
from ..schemas import (
    CitationSummaryResponse,
    CitedSummarySentence,
    EvidenceChunk,
    IngestRequest,
    IngestResponse,
    RetrieveResponse,
    SourceChunkCitation,
    SummaryRequest,
    SummaryResponse,
)
from .chunking import ClinicalChunker
from .embeddings import (
    EmbeddingProvider,
    FastEmbedProvider,
    HashingEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)
from .generators import ExtractiveGenerator, GeminiGroundedGenerator, SummaryGenerator
from .guardrails import GroundingGuardrail
from .telemetry import SummaryTelemetry, SummaryTelemetryEvent, TokenEstimator, build_telemetry
from .vector_store import QdrantVectorStore


class RetrievalError(RuntimeError):
    pass


class RagService:
    def __init__(
        self,
        settings: Settings,
        chunker: ClinicalChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        generator: SummaryGenerator,
        guardrail: GroundingGuardrail,
        telemetry: SummaryTelemetry,
    ):
        self.settings = settings
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.generator = generator
        self.guardrail = guardrail
        self.telemetry = telemetry
        self.token_estimator = TokenEstimator()

    def ingest(
        self,
        tenant_id: str,
        patient_id: str,
        request: IngestRequest,
    ) -> IngestResponse:
        if request.replace_patient_index:
            self.vector_store.delete_patient(tenant_id, patient_id)
        chunks: list[EvidenceChunk] = []
        for document in request.documents:
            chunks.extend(self.chunker.chunk_document(tenant_id, patient_id, document))
        if not chunks:
            raise ValueError("No indexable clinical content was found.")
        vectors = self.embedding_provider.embed_documents([chunk.text for chunk in chunks])
        self.vector_store.upsert(tenant_id, chunks, vectors)
        return IngestResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            documents_received=len(request.documents),
            chunks_indexed=len(chunks),
            embedding_provider=self.embedding_provider.name,
            vector_collection=self.settings.qdrant_collection,
        )

    def retrieve(
        self,
        tenant_id: str,
        patient_id: str,
        query: str,
        top_k: int,
    ) -> RetrieveResponse:
        query_vector = self.embedding_provider.embed_query(query)
        evidence = self.vector_store.search(
            tenant_id,
            patient_id,
            query_vector,
            top_k,
            self.settings.minimum_retrieval_score or None,
        )
        return RetrieveResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            query=query,
            evidence=evidence,
        )

    def summarize(
        self,
        tenant_id: str,
        patient_id: str,
        request: SummaryRequest,
    ) -> SummaryResponse:
        started_at = perf_counter()
        retrieved = self.retrieve(tenant_id, patient_id, request.clinical_question, request.top_k)
        if not retrieved.evidence:
            raise RetrievalError("No patient evidence matched the requested summary scope.")
        candidate = self.generator.generate(
            request.clinical_question,
            request.workflow,
            retrieved.evidence,
        )
        report = self.guardrail.evaluate(candidate, retrieved.evidence)
        status = "accepted" if report.approved else "blocked"
        self.telemetry.record(
            SummaryTelemetryEvent(
                workflow=request.workflow,
                generator_provider=self.generator.name,
                embedding_provider=self.embedding_provider.name,
                latency_ms=(perf_counter() - started_at) * 1000,
                input_tokens=self.token_estimator.input_tokens(request, retrieved.evidence),
                output_tokens=self.token_estimator.output_tokens(candidate),
                retrieved_chunks=len(retrieved.evidence),
                status=status,
                guardrail=report,
            )
        )
        return SummaryResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            status=status,
            workflow=request.workflow,
            generator_provider=self.generator.name,
            evidence=retrieved.evidence,
            summary=candidate if report.approved else None,
            guardrail=report,
        )

    def summarize_with_citations(
        self,
        tenant_id: str,
        patient_id: str,
        request: SummaryRequest,
    ) -> CitationSummaryResponse:
        result = self.summarize(tenant_id, patient_id, request)
        sentences: list[CitedSummarySentence] = []
        if result.status == "accepted" and result.summary is not None:
            evidence_by_id = {item.chunk_id: item for item in result.evidence}
            for claim in result.summary.claims:
                chunks = [evidence_by_id[item] for item in claim.evidence_ids]
                sentences.append(
                    CitedSummarySentence(
                        summary_sentence=claim.text,
                        citations=claim.evidence_ids,
                        source_chunks=[
                            SourceChunkCitation(
                                citation_id=chunk.chunk_id,
                                document_id=chunk.document_id,
                                document_type=chunk.document_type,
                                section=chunk.section,
                                text=chunk.text,
                                char_start=chunk.char_start,
                                char_end=chunk.char_end,
                            )
                            for chunk in chunks
                        ],
                    )
                )
        return CitationSummaryResponse(
            tenant_id=result.tenant_id,
            patient_id=result.patient_id,
            status=result.status,
            workflow=result.workflow,
            generator_provider=result.generator_provider,
            sentences=sentences,
            evidence=result.evidence,
            guardrail=result.guardrail,
        )


def build_rag_service(settings: Settings) -> RagService:
    if settings.embedding_provider == "fastembed":
        embedding_provider: EmbeddingProvider = FastEmbedProvider(
            settings.fastembed_model,
            settings.ort_execution_provider,
            settings.ort_intra_op_threads,
        )
    elif settings.embedding_provider == "sentence_transformers":
        embedding_provider = SentenceTransformersEmbeddingProvider(
            settings.sentence_transformers_model,
            local_files_only=settings.sentence_transformers_local_files_only,
        )
    else:
        embedding_provider = HashingEmbeddingProvider(settings.embedding_dimension)
    api_key = (
        settings.qdrant_api_key.get_secret_value()
        if settings.qdrant_api_key
        else None
    )
    vector_store = QdrantVectorStore(
        settings.qdrant_collection,
        embedding_provider.dimension,
        path=None if settings.qdrant_url else settings.qdrant_path,
        url=settings.qdrant_url,
        api_key=api_key,
    )
    if settings.generator_provider == "gemini":
        assert settings.gemini_api_key is not None
        generator: SummaryGenerator = GeminiGroundedGenerator(
            settings.gemini_api_key.get_secret_value(),
            settings.gemini_model,
        )
    else:
        generator = ExtractiveGenerator()
    guardrail = GroundingGuardrail(
        embedding_provider,
        settings.minimum_token_overlap,
        settings.minimum_semantic_support,
    )
    telemetry = build_telemetry(settings)
    return RagService(
        settings,
        ClinicalChunker(settings.chunk_max_chars, settings.chunk_overlap_sentences),
        embedding_provider,
        vector_store,
        generator,
        guardrail,
        telemetry,
    )
