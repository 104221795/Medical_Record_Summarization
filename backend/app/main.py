from pathlib import Path
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .db.session import build_engine_from_settings, create_session_factory
from .evaluation.artifact_paths import configured_evaluation_artifact_root
from .routers.audit import router as audit_router
from .routers.auth import router as auth_router
from .routers.citations import router as citation_router
from .routers.clinical import router as clinical_router
from .routers.claims import router as claim_router
from .routers.demo import router as demo_router
from .routers.documents import router as document_router
from .routers.encounters import router as encounter_router
from .routers.evaluation import router as evaluation_router
from .routers.fhir import router as fhir_router
from .routers.ingestion import router as ingestion_router
from .routers.jobs import router as jobs_router
from .routers.metrics import router as metrics_router
from .routers.multimodal import router as multimodal_router
from .routers.patients import router as patient_router
from .routers.providers import router as provider_router
from .routers.rag import router as rag_router
from .routers.summaries import router as summary_router
from .schemas import HealthResponse
from .services.background_jobs import model_job_service
from .services.clinical_pipeline import ClinicalSummaryPipelineService
from .services.fhir_mapper import FhirMapperService
from .services.multimodal import MultimodalService
from .services.rag import RagService, build_rag_service
from .services.llm_gateway import SummaryProviderGateway
from .models import ModelJobRecord
from sqlalchemy import func, select


CITATION_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "citation"
DOCTOR_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "doctor"
ADMIN_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "admin"
EVALUATION_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "evaluation"
UNIFIED_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "unified"
ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    rag_service: RagService | None = None,
    multimodal_service: MultimodalService | None = None,
    fhir_mapper_service: FhirMapperService | None = None,
    db_session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    configured_settings = settings or get_settings()
    app = FastAPI(
        title=configured_settings.app_name,
        version="0.3.0-fhir-mapper",
        description=(
            "Evidence-grounded medical record summarization with multi-modal input processing. "
            "Generated output is an AI draft and requires clinician review."
        ),
    )
    app.state.settings = configured_settings
    cors_origins = _parse_csv(configured_settings.cors_origins)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def enforce_request_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > configured_settings.maximum_request_bytes
            except ValueError:
                too_large = False
            if too_large:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": (
                            "Request body exceeds the configured staging size limit."
                        )
                    },
                )
        return await call_next(request)
    app.state.db_session_factory = db_session_factory or create_session_factory(
        build_engine_from_settings(configured_settings)
    )
    app.state.rag_service = rag_service or build_rag_service(configured_settings)
    app.state.summary_model_providers = {}
    app.state.clinical_pipeline_service = ClinicalSummaryPipelineService(app.state.rag_service)
    app.state.multimodal_service = multimodal_service or MultimodalService(configured_settings)
    app.state.fhir_mapper_service = fhir_mapper_service or FhirMapperService(configured_settings)
    model_job_service.configure_runtime(
        db_session_factory=app.state.db_session_factory,
        settings=app.state.settings,
        rag_service=app.state.rag_service,
        summary_model_providers=app.state.summary_model_providers,
        gemini_json_client=getattr(app.state, "gemini_json_client", None),
    )

    @app.exception_handler(OperationalError)
    async def database_operational_error(
        _request: Request, _exc: OperationalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": (
                    "Database is unavailable or the local schema is not initialized. "
                    "Run Alembic migrations, or use /api/v1/demo/seed in development."
                )
            },
        )

    app.include_router(rag_router, prefix=configured_settings.api_prefix)
    app.include_router(auth_router, prefix=configured_settings.api_prefix)
    app.include_router(patient_router, prefix=configured_settings.api_prefix)
    app.include_router(encounter_router, prefix=configured_settings.api_prefix)
    app.include_router(document_router, prefix=configured_settings.api_prefix)
    app.include_router(ingestion_router, prefix=configured_settings.api_prefix)
    app.include_router(audit_router, prefix=configured_settings.api_prefix)
    app.include_router(metrics_router, prefix=configured_settings.api_prefix)
    app.include_router(summary_router, prefix=configured_settings.api_prefix)
    app.include_router(provider_router, prefix=configured_settings.api_prefix)
    app.include_router(jobs_router, prefix=configured_settings.api_prefix)
    app.include_router(claim_router, prefix=configured_settings.api_prefix)
    app.include_router(citation_router, prefix=configured_settings.api_prefix)
    app.include_router(demo_router, prefix=configured_settings.api_prefix)
    app.include_router(evaluation_router, prefix=configured_settings.api_prefix)
    app.include_router(clinical_router, prefix=configured_settings.api_prefix)
    app.include_router(multimodal_router, prefix=configured_settings.api_prefix)
    app.include_router(fhir_router, prefix=configured_settings.api_prefix)
    _log_registered_auth_routes(app)
    app.mount("/citation-assets", StaticFiles(directory=CITATION_UI_DIR), name="citation-assets")
    app.mount("/doctor-assets", StaticFiles(directory=DOCTOR_UI_DIR), name="doctor-assets")
    app.mount("/admin-assets", StaticFiles(directory=ADMIN_UI_DIR), name="admin-assets")
    app.mount(
        "/evaluation-assets",
        StaticFiles(directory=EVALUATION_UI_DIR),
        name="evaluation-assets",
    )
    app.mount(
        "/demo-console-assets",
        StaticFiles(directory=UNIFIED_UI_DIR),
        name="demo-console-assets",
    )

    @app.get("/citation-demo", include_in_schema=False)
    def citation_demo() -> FileResponse:
        return FileResponse(CITATION_UI_DIR / "index.html")

    @app.get("/doctor-demo", include_in_schema=False)
    def doctor_demo() -> FileResponse:
        return FileResponse(DOCTOR_UI_DIR / "index.html")

    @app.get("/admin/dashboard", include_in_schema=False)
    def admin_dashboard() -> FileResponse:
        return FileResponse(ADMIN_UI_DIR / "index.html")

    @app.get("/evaluation-demo", include_in_schema=False)
    def evaluation_demo() -> FileResponse:
        return FileResponse(EVALUATION_UI_DIR / "index.html")

    @app.get("/demo-console", include_in_schema=False)
    def demo_console() -> FileResponse:
        return FileResponse(UNIFIED_UI_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse, tags=["Operations"])
    @app.get("/healthz", response_model=HealthResponse, tags=["Operations"])
    def health() -> HealthResponse:
        service = app.state.rag_service
        return HealthResponse(
            status="ok",
            service=configured_settings.app_name,
            embedding_provider=service.embedding_provider.name,
            generator_provider=service.generator.name,
            speech_model=configured_settings.whisper_model,
            vision_model=configured_settings.vit_model,
            fhir_endpoint_mode="validated-mock-transaction",
            ort_execution_provider=configured_settings.ort_execution_provider,
            mlflow_enabled=configured_settings.mlflow_enabled,
        )

    @app.get("/ready", tags=["Operations"])
    def ready() -> JSONResponse:
        report = _readiness_report(app)
        http_status = status.HTTP_200_OK if report["status"] in {"ready", "degraded"} else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=report)

    if FRONTEND_DIST_DIR.exists():
        assets_dir = FRONTEND_DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(FRONTEND_DIST_DIR / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend_spa(full_path: str):
            api_prefix = configured_settings.api_prefix.strip("/")
            if full_path == api_prefix or full_path.startswith(f"{api_prefix}/"):
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "API route was not found."},
                )
            requested = (FRONTEND_DIST_DIR / full_path).resolve()
            if requested.is_file() and FRONTEND_DIST_DIR.resolve() in requested.parents:
                return FileResponse(requested)
            return FileResponse(FRONTEND_DIST_DIR / "index.html")

    return app


def _log_registered_auth_routes(app: FastAPI) -> None:
    api_prefix = getattr(app.state.settings, "api_prefix", "/api/v1")
    auth_routes = sorted(
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith(f"{api_prefix}/auth")
    )
    logger.info("Registered authentication routes: %s", ", ".join(auth_routes))


def _readiness_report(app: FastAPI) -> dict[str, Any]:
    settings = app.state.settings
    job_readiness = model_job_service.readiness(include_smoke=False)
    provider_readiness = SummaryProviderGateway(settings).list_providers()
    checks: dict[str, dict[str, Any]] = {
        "database": _database_check(app.state.db_session_factory),
        "vector_store": _vector_store_check(settings),
        "artifacts": _artifact_check(settings),
        "providers": _provider_catalog_check(settings, provider_readiness.providers),
        "jobs": _job_system_check(
            app.state.db_session_factory,
            settings,
            job_readiness.queue_status,
        ),
        "configuration": _configuration_check(settings),
    }
    critical_names = ["database", "configuration"]
    if settings.redis_required or settings.deployment_mode in {"compose", "railway"}:
        critical_names.append("jobs")
    critical_failures = [
        name for name in critical_names if checks[name]["status"] == "fail"
    ]
    degraded = any(item["status"] in {"warning", "fail"} for item in checks.values())
    return {
        "status": "not_ready" if critical_failures else ("degraded" if degraded else "ready"),
        "service": settings.app_name,
        "environment": settings.environment,
        "deployment_mode": settings.deployment_mode,
        "api_prefix": settings.api_prefix,
        "checks": checks,
        "clinical_use": "staging_demo_only",
        "disclaimer": (
            "AI-generated summaries are drafts for clinician review only. "
            "This deployment must use de-identified/demo data and is not clinical validation."
        ),
    }


def _database_check(factory: sessionmaker[Session]) -> dict[str, Any]:
    try:
        session = factory()
        try:
            session.execute(text("select 1"))
            return {"status": "pass", "message": "Database connection is available."}
        finally:
            session.close()
    except Exception as exc:
        return {
            "status": "fail",
            "message": "Database connection failed.",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _vector_store_check(settings: Settings) -> dict[str, Any]:
    if settings.qdrant_url:
        return {
            "status": "warning",
            "mode": "remote_qdrant_configured",
            "message": "Remote Qdrant URL is configured; live vector-store ping is not required for API readiness.",
        }
    if settings.qdrant_path:
        return {
            "status": "pass" if settings.qdrant_path.exists() else "warning",
            "mode": "local_path",
            "path": str(settings.qdrant_path),
            "message": "Local Qdrant path exists." if settings.qdrant_path.exists() else "Local Qdrant path does not exist yet; it can be created on first demo use.",
        }
    return {
        "status": "warning",
        "mode": "in_memory_or_unconfigured",
        "message": "No remote Qdrant URL/path configured. Local demo retrieval may use in-process storage.",
    }


def _artifact_check(settings: Settings) -> dict[str, Any]:
    root = configured_evaluation_artifact_root(settings.evaluation_artifact_root)
    return {
        "status": "pass" if root.exists() else "warning",
        "path": str(root),
        "message": (
            "Evaluation artifact root is readable."
            if root.exists()
            else (
                "Evaluation artifact root does not exist yet. Set "
                "RAG_EVALUATION_ARTIFACT_ROOT or prepare artifacts/evaluation."
            )
        ),
    }


def _provider_catalog_check(settings: Settings, providers: list[Any]) -> dict[str, Any]:
    primary = next(
        (item for item in providers if item.provider_name == settings.primary_provider),
        None,
    )
    ready_count = sum(1 for item in providers if item.selectable)
    primary_ready = bool(primary and primary.selectable)
    return {
        "status": "pass" if primary_ready else "warning",
        "provider_count": len(providers),
        "selectable_count": ready_count,
        "primary_provider": settings.primary_provider,
        "primary_ready": primary_ready,
        "primary_status": primary.status if primary else "unregistered",
        "primary_disabled_reason": primary.disabled_reason if primary else "Provider is not registered.",
        "providers": [item.model_dump(mode="json") for item in providers],
        "message": (
            "Primary provider is selectable."
            if primary_ready
            else "Primary provider is unavailable; deterministic smoke fallback may remain available."
        ),
    }


def _job_system_check(
    factory: sessionmaker[Session],
    settings: Settings,
    queue_status: dict[str, Any],
) -> dict[str, Any]:
    active_jobs = 0
    try:
        session = factory()
        try:
            active_jobs = int(
                session.scalar(
                    select(func.count())
                    .select_from(ModelJobRecord)
                    .where(ModelJobRecord.status.in_(["queued", "running"]))
                )
                or 0
            )
        finally:
            session.close()
    except Exception:
        active_jobs = -1
    redis_reachable = bool(queue_status.get("redis_reachable"))
    worker_count = int(queue_status.get("worker_count") or 0)
    required = settings.redis_required or settings.deployment_mode in {"compose", "railway"}
    ready = (
        settings.background_jobs_enabled
        and settings.job_backend == "rq"
        and redis_reachable
        and worker_count >= 1
    )
    if not settings.background_jobs_enabled:
        state = "fail" if required else "warning"
        message = "Background jobs are disabled."
    elif settings.job_backend != "rq":
        state = "fail" if required else "warning"
        message = "Background jobs are not configured for Redis/RQ."
    elif not redis_reachable:
        state = "fail" if required else "warning"
        message = "Redis is unavailable."
    elif worker_count < 1:
        state = "fail" if required else "warning"
        message = "Redis is reachable, but no live worker is registered."
    else:
        state = "pass"
        message = "Redis queue and worker are ready."
    return {
        "status": state,
        "required": required,
        "ready": ready,
        "backend": settings.job_backend,
        "redis_reachable": redis_reachable,
        "worker_count": worker_count,
        "workers": [
            *(queue_status.get("rq_workers") or []),
            *(queue_status.get("windows_workers") or []),
        ],
        "queued_count": queue_status.get("queued_count"),
        "active_job_count": active_jobs,
        "queue_name": queue_status.get("queue_name"),
        "message": message,
    }


def _configuration_check(settings: Settings) -> dict[str, Any]:
    warnings: list[str] = []
    if settings.deployment_mode == "railway" and settings.cors_origins.startswith("http://"):
        warnings.append("Set CORS_ORIGINS to the deployed HTTPS frontend domain.")
    if settings.environment == "production":
        warnings.append("Production clinical deployment is not supported by this PoC; use staging/demo only.")
    return {
        "status": "warning" if warnings else "pass",
        "warnings": warnings,
        "message": "Configuration is valid for staging demo." if not warnings else "Configuration has deployment warnings.",
    }


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


app = create_app()
