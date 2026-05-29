from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .db.session import build_engine_from_settings, create_session_factory
from .routers.audit import router as audit_router
from .routers.citations import router as citation_router
from .routers.clinical import router as clinical_router
from .routers.claims import router as claim_router
from .routers.demo import router as demo_router
from .routers.documents import router as document_router
from .routers.encounters import router as encounter_router
from .routers.evaluation import router as evaluation_router
from .routers.fhir import router as fhir_router
from .routers.ingestion import router as ingestion_router
from .routers.metrics import router as metrics_router
from .routers.multimodal import router as multimodal_router
from .routers.patients import router as patient_router
from .routers.rag import router as rag_router
from .routers.summaries import router as summary_router
from .schemas import HealthResponse
from .services.clinical_pipeline import ClinicalSummaryPipelineService
from .services.fhir_mapper import FhirMapperService
from .services.multimodal import MultimodalService
from .services.rag import RagService, build_rag_service


CITATION_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "citation"
DOCTOR_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "doctor"
ADMIN_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "admin"
EVALUATION_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "evaluation"
UNIFIED_UI_DIR = Path(__file__).resolve().parents[1] / "ui" / "unified"


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
    app.state.db_session_factory = db_session_factory or create_session_factory(
        build_engine_from_settings(configured_settings)
    )
    app.state.rag_service = rag_service or build_rag_service(configured_settings)
    app.state.clinical_pipeline_service = ClinicalSummaryPipelineService(app.state.rag_service)
    app.state.multimodal_service = multimodal_service or MultimodalService(configured_settings)
    app.state.fhir_mapper_service = fhir_mapper_service or FhirMapperService(configured_settings)

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
    app.include_router(patient_router, prefix=configured_settings.api_prefix)
    app.include_router(encounter_router, prefix=configured_settings.api_prefix)
    app.include_router(document_router, prefix=configured_settings.api_prefix)
    app.include_router(ingestion_router, prefix=configured_settings.api_prefix)
    app.include_router(audit_router, prefix=configured_settings.api_prefix)
    app.include_router(metrics_router, prefix=configured_settings.api_prefix)
    app.include_router(summary_router, prefix=configured_settings.api_prefix)
    app.include_router(claim_router, prefix=configured_settings.api_prefix)
    app.include_router(citation_router, prefix=configured_settings.api_prefix)
    app.include_router(demo_router, prefix=configured_settings.api_prefix)
    app.include_router(evaluation_router, prefix=configured_settings.api_prefix)
    app.include_router(clinical_router, prefix=configured_settings.api_prefix)
    app.include_router(multimodal_router, prefix=configured_settings.api_prefix)
    app.include_router(fhir_router, prefix=configured_settings.api_prefix)
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

    return app


app = create_app()
