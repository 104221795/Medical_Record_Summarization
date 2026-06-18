from __future__ import annotations

import argparse
import json
import os
import threading
import time
from uuid import UUID

from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.session import build_engine_from_settings, create_session_factory
from backend.app.models import ClinicalDocument, Encounter, Patient
from backend.app.persistence_schemas import ModelJobCreateRequest
from backend.app.runtime_env import load_runtime_env
from backend.app.services.background_jobs import ModelJobService


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real Redis/RQ doctor-summary provider smoke test on the configured database."
    )
    parser.add_argument("--provider", default="qwen2.5", help="Provider to smoke test, for example qwen2.5 or llama3.2.")
    parser.add_argument("--queue", default="clin_summ_provider_smoke", help="Isolated RQ queue for the smoke test.")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--patient-id", default=None)
    parser.add_argument("--encounter-id", default=None)
    parser.add_argument("--run-worker-burst", action="store_true")
    parser.add_argument(
        "--worker-class",
        choices=("windows", "simple", "spawn", "default"),
        default="windows",
        help="Use windows for local heavy model jobs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_runtime_env(enable_model_defaults=True, job_backend="rq")
    os.environ["RAG_RQ_QUEUE_NAME"] = args.queue
    settings = get_settings().model_copy(
        update={
            "job_backend": "rq",
            "rq_queue_name": args.queue,
            "job_fallback_to_in_process": False,
            "rq_require_live_worker": False,
        }
    )
    session_factory = create_session_factory(build_engine_from_settings(settings))
    patient_id, encounter_id = _resolve_patient_scope(
        session_factory,
        patient_id=args.patient_id,
        encounter_id=args.encounter_id,
    )
    service = ModelJobService(max_workers=1)
    service.configure_runtime(
        db_session_factory=session_factory,
        settings=settings,
        rag_service=None,
        mark_interrupted=False,
    )
    created = service.enqueue_summary_generation(
        patient_id=str(patient_id),
        request_payload={
            "encounter_id": str(encounter_id) if encounter_id else None,
            "summary_type": "patient_snapshot",
            "language": "en",
            "provider": args.provider,
            "model_provider": args.provider,
            "options": {"require_citations": True, "include_safety_check": True},
        },
        tenant_id="sandbox",
        actor_external_id="rq-smoke",
        model_provider=args.provider,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"enqueued": created.model_dump(mode="json")}, indent=2))
    if args.run_worker_burst:
        if args.worker_class == "windows":
            _run_worker_burst(settings.redis_url, args.queue, args.worker_class)
        else:
            stop_monitor = threading.Event()
            monitor = threading.Thread(
                target=_monitor_job,
                args=(service, created.job_id, stop_monitor),
                daemon=True,
            )
            monitor.start()
            try:
                _run_worker_burst(settings.redis_url, args.queue, args.worker_class)
            finally:
                stop_monitor.set()
                monitor.join(timeout=1.0)
    final = _wait_for_job(service, created.job_id, args.timeout_seconds + 15)
    print(json.dumps({"final": final.model_dump(mode="json") if final else None}, indent=2))
    if final is None or final.status != "completed":
        raise SystemExit(1)


def _resolve_patient_scope(session_factory, *, patient_id: str | None, encounter_id: str | None) -> tuple[UUID, UUID | None]:
    session = session_factory()
    try:
        if patient_id:
            patient = session.get(Patient, UUID(patient_id))
            if patient is None:
                raise SystemExit(f"Patient not found: {patient_id}")
        else:
            patient = session.scalars(
                select(Patient)
                .join(Encounter, Encounter.patient_id == Patient.patient_id)
                .join(ClinicalDocument, ClinicalDocument.patient_id == Patient.patient_id)
                .order_by(Patient.created_at.desc())
            ).first()
            if patient is None:
                raise SystemExit("No patients with clinical documents found. Import or seed de-identified demo data first.")
        if encounter_id:
            encounter = session.get(Encounter, UUID(encounter_id))
            if encounter is None:
                raise SystemExit(f"Encounter not found: {encounter_id}")
        else:
            encounter = session.scalars(
                select(Encounter)
                .where(Encounter.patient_id == patient.patient_id)
                .order_by(Encounter.created_at.desc())
            ).first()
        return patient.patient_id, encounter.encounter_id if encounter else None
    finally:
        session.close()


def _run_worker_burst(redis_url: str, queue_name: str, worker_class: str) -> None:
    redis_connection = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=redis_connection)
    from rq import SpawnWorker, Worker

    if worker_class == "windows":
        from scripts.run_rq_worker import _run_windows_worker

        _run_windows_worker(queue, redis_connection, burst=True)
        return
    worker_cls = {"simple": SimpleWorker, "spawn": SpawnWorker, "default": Worker}[worker_class]
    worker = worker_cls([queue], connection=redis_connection)
    worker.work(burst=True)


def _monitor_job(service: ModelJobService, job_id: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        latest = service.get(job_id)
        if latest is not None:
            line = (
                f"[monitor {time.strftime('%H:%M:%S')}] "
                f"[monitor] status={latest.status} "
                f"progress={latest.progress:.2f} step={latest.current_step or 'n/a'}"
            )
            if latest.error_message:
                line += f" error={latest.error_message}"
            print(line, flush=True)
            if latest.status in TERMINAL_STATUSES:
                return
        stop_event.wait(5.0)


def _wait_for_job(service: ModelJobService, job_id: str, timeout_seconds: float):
    deadline = time.perf_counter() + timeout_seconds
    latest = None
    while time.perf_counter() < deadline:
        latest = service.get(job_id)
        if latest and latest.status in TERMINAL_STATUSES:
            return latest
        time.sleep(0.5)
    return latest


if __name__ == "__main__":
    main()
