from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"

# Pydantic can read values from .env, but Hugging Face, Ollama, LiteLLM,
# and a few local scripts read directly from os.environ. Loading the file here
# keeps one persistent local runtime config instead of long PowerShell env blocks.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    """Configuration loaded from environment or the repository .env file."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="RAG_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Medical Record Summarization RAG API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    deployment_mode: Literal["local", "railway"] = Field(
        default="local",
        validation_alias=AliasChoices("RAG_DEPLOYMENT_MODE", "DEPLOYMENT_MODE"),
    )
    primary_provider: str = Field(
        default="deterministic",
        validation_alias=AliasChoices("RAG_PRIMARY_PROVIDER", "PRIMARY_PROVIDER"),
    )
    api_prefix: str = "/api/v1"
    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        validation_alias=AliasChoices("RAG_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    evaluation_artifact_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAG_EVALUATION_ARTIFACT_ROOT",
            "EVALUATION_ARTIFACT_ROOT",
            "BENCHMARK_SNAPSHOT_DIR",
        ),
    )

    database_url: str = Field(
        default="sqlite:///./var/clin_summ.db",
        validation_alias=AliasChoices("RAG_DATABASE_URL", "DATABASE_URL"),
    )
    database_echo: bool = False

    job_backend: Literal["in_process", "rq"] = Field(
        default="in_process",
        validation_alias=AliasChoices("RAG_JOB_BACKEND", "JOB_BACKEND"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("RAG_REDIS_URL", "REDIS_URL"),
    )
    job_fallback_to_in_process: bool = Field(
        default=True,
        validation_alias=AliasChoices("RAG_JOB_FALLBACK_TO_IN_PROCESS", "JOB_FALLBACK_TO_IN_PROCESS"),
    )
    rq_queue_name: str = Field(
        default="clin_summ_jobs",
        validation_alias=AliasChoices("RAG_RQ_QUEUE_NAME", "RQ_QUEUE_NAME"),
    )
    rq_require_live_worker: bool = Field(
        default=True,
        validation_alias=AliasChoices("RAG_RQ_REQUIRE_LIVE_WORKER", "RQ_REQUIRE_LIVE_WORKER"),
    )
    rq_result_ttl_seconds: int = Field(
        default=24 * 60 * 60,
        validation_alias=AliasChoices("RAG_RQ_RESULT_TTL_SECONDS", "RQ_RESULT_TTL_SECONDS"),
    )
    rq_failure_ttl_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        validation_alias=AliasChoices("RAG_RQ_FAILURE_TTL_SECONDS", "RQ_FAILURE_TTL_SECONDS"),
    )
    rq_max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        validation_alias=AliasChoices("RAG_RQ_MAX_RETRIES", "RQ_MAX_RETRIES"),
    )
    rq_worker_heartbeat_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias=AliasChoices(
            "RAG_RQ_WORKER_HEARTBEAT_SECONDS",
            "RQ_WORKER_HEARTBEAT_SECONDS",
        ),
    )
    rq_worker_stale_seconds: int = Field(
        default=20,
        ge=5,
        le=10 * 60,
        validation_alias=AliasChoices("RAG_RQ_WORKER_STALE_SECONDS", "RQ_WORKER_STALE_SECONDS"),
    )

    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_path: Path | None = None
    qdrant_collection: str = "clinical_record_chunks"

    embedding_provider: Literal["hashing", "fastembed", "sentence_transformers"] = "sentence_transformers"
    embedding_dimension: int = 384
    fastembed_model: str = "intfloat/multilingual-e5-large"
    sentence_transformers_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    sentence_transformers_local_files_only: bool = True
    ort_execution_provider: Literal[
        "CPUExecutionProvider",
        "OpenVINOExecutionProvider",
        "CUDAExecutionProvider",
    ] = "CPUExecutionProvider"
    ort_intra_op_threads: int | None = None

    generator_provider: Literal["extractive", "gemini"] = "extractive"
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_GEMINI_API_KEY", "GEMINI_API_KEY"),
    )
    gemini_model: str = "gemini-2.5-flash-lite"
    google_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID"),
    )
    auth_secret_key: SecretStr = Field(default=SecretStr("dev-change-me-auth-secret"))
    auth_token_ttl_minutes: int = 60 * 12
    allow_demo_header_auth: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "RAG_ALLOW_DEMO_HEADER_AUTH",
            "ALLOW_DEMO_HEADER_AUTH",
        ),
    )
    maximum_request_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1024,
        validation_alias=AliasChoices(
            "RAG_MAXIMUM_REQUEST_BYTES",
            "MAXIMUM_REQUEST_BYTES",
        ),
    )

    local_ollama_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "RAG_LOCAL_OLLAMA_ENABLED",
            "LOCAL_OLLAMA_ENABLED",
        ),
    )
    ollama_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAG_OLLAMA_BASE_URL",
            "OLLAMA_BASE_URL",
            "OLLAMA_API_BASE",
        ),
    )
    background_jobs_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "RAG_BACKGROUND_JOBS_ENABLED",
            "BACKGROUND_JOBS_ENABLED",
        ),
    )
    redis_required: bool = Field(
        default=False,
        validation_alias=AliasChoices("RAG_REDIS_REQUIRED", "REDIS_REQUIRED"),
    )

    llm_provider: Literal["mock", "deterministic", "local", "external", "gemini"] = "deterministic"
    llm_mock_behavior: Literal["normal", "invalid_json", "unsupported_claim"] = "normal"
    llm_external_enabled: bool = False
    llm_allow_phi_external: bool = False
    llm_model_name: str = "mock-clinical-json"
    llm_model_version: str = "phase7-1.0.0"
    llm_temperature: float = 0.0
    prompt_templates_dir: Path = ROOT_DIR / "prompts"

    chunk_max_chars: int = 1200
    chunk_overlap_sentences: int = 1
    retrieval_top_k: int = 6
    minimum_retrieval_score: float = 0.0
    minimum_token_overlap: float = 0.16
    minimum_semantic_support: float = 0.42

    whisper_model: str = "openai/whisper-small"
    whisper_device: int = -1
    vit_model: str = "google/vit-base-patch16-224-in21k"
    vision_device: Literal["cpu", "cuda"] = "cpu"
    maximum_audio_bytes: int = 50 * 1024 * 1024
    maximum_image_bytes: int = 20 * 1024 * 1024

    fhir_mock_base_url: str = "https://hapi.fhir.local/fhir/R4"
    fhir_mapper_device_reference: str = "Device/clinical-summarization-service"
    medical_nli_model_path: Path | None = None
    medical_nli_contradiction_threshold: float = 0.80
    medical_nli_required_for_writeback: bool = False

    mlflow_enabled: bool = False
    mlflow_tracking_uri: str = "sqlite:///./backend/var/mlflow.db"
    mlflow_experiment_name: str = "medical-record-summarization"
    mlflow_log_redacted_safety_artifacts: bool = True

    @model_validator(mode="after")
    def enforce_production_safety(self) -> "Settings":
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        if self.environment in {"staging", "production"}:
            if self.auth_secret_key.get_secret_value() == "dev-change-me-auth-secret":
                raise ValueError(
                    "Staging/production requires RAG_AUTH_SECRET_KEY or AUTH_SECRET_KEY "
                    "to be set to a non-default secret."
                )
            if self.allow_demo_header_auth:
                raise ValueError(
                    "Demo header authentication must be disabled in staging/production."
                )
            if "*" in {origin.strip() for origin in self.cors_origins.split(",")}:
                raise ValueError("Wildcard CORS is not allowed in staging/production.")
        if self.deployment_mode == "railway" and self.job_backend != "rq":
            raise ValueError("Railway deployment requires RAG_JOB_BACKEND=rq.")
        if self.deployment_mode == "railway" and not self.redis_required:
            raise ValueError("Railway deployment requires REDIS_REQUIRED=true.")
        if self.environment == "production" and self.embedding_provider == "hashing":
            raise ValueError(
                "Hashing embeddings are development-only; configure "
                "RAG_EMBEDDING_PROVIDER=sentence_transformers with "
                "RAG_SENTENCE_TRANSFORMERS_MODEL=sentence-transformers/all-MiniLM-L6-v2 "
                "or another approved production embedding backend."
            )
        if self.environment == "production" and not self.qdrant_url:
            raise ValueError("Production requires RAG_QDRANT_URL for a shared Qdrant server.")
        if self.ort_execution_provider != "CPUExecutionProvider" and self.embedding_provider != "fastembed":
            raise ValueError("Accelerated ONNX execution providers require embedding_provider=fastembed.")
        if self.generator_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("RAG_GEMINI_API_KEY is required when generator_provider=gemini.")
        if self.llm_provider in {"external", "gemini"} and not self.llm_external_enabled:
            raise ValueError(
                "RAG_LLM_EXTERNAL_ENABLED=true is required when RAG_LLM_PROVIDER is external or gemini."
            )
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("RAG_GEMINI_API_KEY is required when RAG_LLM_PROVIDER=gemini.")
        if self.llm_external_enabled and not self.llm_allow_phi_external:
            raise ValueError(
                "External LLM access requires RAG_LLM_ALLOW_PHI_EXTERNAL=true after governance approval."
            )
        if not 0.0 <= self.llm_temperature <= 2.0:
            raise ValueError("RAG_LLM_TEMPERATURE must be between 0 and 2.")
        if self.medical_nli_required_for_writeback and not self.medical_nli_model_path:
            raise ValueError(
                "RAG_MEDICAL_NLI_MODEL_PATH is required when medical NLI is mandatory for writeback."
            )
        if self.environment == "production" and not self.medical_nli_required_for_writeback:
            raise ValueError("Production FHIR writeback requires medical NLI validation.")
        if not 0.0 <= self.medical_nli_contradiction_threshold <= 1.0:
            raise ValueError("RAG_MEDICAL_NLI_CONTRADICTION_THRESHOLD must be between 0 and 1.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
