from __future__ import annotations

import os
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from rag_app.auth import create_access_token, read_access_token, seed_demo_users, verify_password
from rag_app.db import AuditEvent, Base, ChatRequestRecord, DailyTokenBudget, Document, DocumentVersion, IngestionJob, User, make_engine, make_session_factory, now_utc
from rag_app.evaluation_dashboard import load_evaluation_dashboard
from rag_app.generation import AnswerProvider, GlmAnswerProvider, cited_sources
from rag_app.ingestion import run_index_job, run_purge_job, stage_document
from rag_app.init_db import require_current_schema
from rag_app.lexical_index import ChineseBm25, LexicalIndex
from rag_app.lifecycle import LifecycleError, activate_version, delete_document, retry_job, visible_version_ids
from rag_app.quota import estimate_token_reservation, finish_chat_request, reconcile_stale_reservations, reserve_tokens, settle_tokens
from rag_app.retrieval import retrieve
from rag_app.reranker import BgeReranker, Reranker
from rag_app.vector_index import BgeEmbedder, Embedder, VectorIndex


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def process_local_jobs(app: FastAPI) -> None:
    with app.state.job_lock:
        while True:
            with app.state.sessions() as session:
                job = session.scalar(
                    select(IngestionJob).where(IngestionJob.status == "PENDING")
                    .order_by(IngestionJob.created_at, IngestionJob.id).limit(1)
                )
                job_id, kind = (job.id, job.kind) if job else (None, None)
            if job_id is None:
                return
            try:
                if kind == "index":
                    if app.state.embedder is None:
                        app.state.embedder = app.state.embedder_factory()
                    if app.state.lexical_index is not None and app.state.bm25 is None:
                        app.state.bm25 = app.state.bm25_factory()
                    run_index_job(
                        app.state.sessions, app.state.index, app.state.embedder, job_id,
                        lexical_index=app.state.lexical_index, bm25=app.state.bm25,
                    )
                elif kind == "purge":
                    run_purge_job(app.state.sessions, app.state.index, job_id, lexical_index=app.state.purge_lexical_index)
                else:
                    raise ValueError(f"Unsupported job kind: {kind}")
            except Exception as exc:
                with app.state.sessions.begin() as session:
                    failed_job = session.get(IngestionJob, job_id)
                    if failed_job is not None:
                        failed_job.status = "FAILED"
                        failed_job.error = str(exc)[:2000]
                        failed_job.finished_at = now_utc()
                        version = session.get(DocumentVersion, failed_job.version_id)
                        if version is not None and kind == "index":
                            version.status = "FAILED"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


def create_app(
    *,
    database_url: str | None = None,
    qdrant_client: QdrantClient | None = None,
    embedder_factory: Callable[[], Embedder] = BgeEmbedder,
    bm25_factory: Callable[[], ChineseBm25] = ChineseBm25,
    reranker_factory: Callable[[], Reranker] = BgeReranker,
    answer_provider_factory: Callable[[], AnswerProvider] = GlmAnswerProvider,
    seed_demo: bool | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(database_url)
        if engine.dialect.name == "sqlite":
            if inspect(engine).has_table("alembic_version"):
                require_current_schema(engine)
            else:
                Base.metadata.create_all(engine)
        else:
            require_current_schema(engine)
        app.state.sessions = make_session_factory(engine)
        reconcile_stale_reservations(app.state.sessions)
        local_path = os.getenv("QDRANT_LOCAL_PATH") if qdrant_client is None else None
        if local_path:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=local_path)
        else:
            client = qdrant_client or QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        app.state.index = VectorIndex(client)
        retrieval_mode = os.getenv("RETRIEVAL_MODE", "dense")
        if retrieval_mode not in {"dense", "hybrid"}:
            raise ValueError("RETRIEVAL_MODE must be dense or hybrid")
        app.state.lexical_index = LexicalIndex(client) if retrieval_mode == "hybrid" else None
        app.state.purge_lexical_index = LexicalIndex(client)
        app.state.bm25_factory = bm25_factory
        app.state.bm25 = None
        app.state.reranker_factory = reranker_factory
        app.state.reranker = None
        app.state.enable_reranker = os.getenv("ENABLE_RERANKER", "0") == "1"
        app.state.inline_jobs = bool(local_path)
        app.state.job_lock = threading.Lock()
        app.state.embedder_factory = embedder_factory
        app.state.embedder = None
        app.state.answer_provider_factory = answer_provider_factory
        app.state.answer_provider = None
        llm_enabled = os.getenv("LLM_ENABLED", "1")
        if llm_enabled not in {"0", "1"}:
            raise ValueError("LLM_ENABLED must be 0 or 1")
        app.state.llm_enabled = llm_enabled == "1"
        app.state.daily_token_limit = int(os.getenv("LLM_DAILY_TOKEN_LIMIT", "50000"))
        if app.state.daily_token_limit < 0:
            raise ValueError("LLM_DAILY_TOKEN_LIMIT must be nonnegative")
        app.state.jwt_secret = os.getenv("JWT_SECRET") or secrets.token_urlsafe(32)
        app.state.storage_root = Path(os.getenv("STORAGE_ROOT", ".data/uploads"))
        use_demo = seed_demo if seed_demo is not None else os.getenv("SEED_DEMO_USERS") == "1"
        if use_demo:
            with app.state.sessions.begin() as session:
                seed_demo_users(session, os.getenv("DEMO_PASSWORD", "demo12345"))
        yield
        if local_path:
            client.close()
        engine.dispose()

    api = FastAPI(title="Enterprise RAG Assistant", version="0.2.0", lifespan=lifespan)

    def get_session(request: Request):
        with request.app.state.sessions() as session:
            yield session

    def current_user(
        request: Request,
        token: str = Depends(oauth2_scheme),
        session: Session = Depends(get_session),
    ) -> User:
        user_id = read_access_token(token, request.app.state.jwt_secret)
        user = session.get(User, user_id) if user_id else None
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user

    def admin_user(user: User = Depends(current_user)) -> User:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator required")
        return user

    def find_hits(request: Request, query: str, version_ids: list[str], limit: int):
        if not version_ids or not request.app.state.index.client.collection_exists(request.app.state.index.collection):
            return []
        if request.app.state.embedder is None:
            request.app.state.embedder = request.app.state.embedder_factory()
        if request.app.state.lexical_index is not None and request.app.state.bm25 is None:
            request.app.state.bm25 = request.app.state.bm25_factory()
        if request.app.state.enable_reranker and request.app.state.reranker is None:
            request.app.state.reranker = request.app.state.reranker_factory()
        return retrieve(
            query, version_ids, limit, request.app.state.index, request.app.state.embedder,
            request.app.state.lexical_index, request.app.state.bm25, request.app.state.reranker,
        )

    def still_visible(session: Session, user: User, hits):
        session.expire_all()
        current_ids = set(visible_version_ids(session, user.role, user.department))
        return [hit for hit in hits if hit.version_id in current_ids]

    @api.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/api/v1/auth/login")
    def login(
        request: Request,
        form: OAuth2PasswordRequestForm = Depends(),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        user = session.scalar(select(User).where(User.username == form.username))
        if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"access_token": create_access_token(user.id, request.app.state.jwt_secret), "token_type": "bearer"}

    @api.get("/api/v1/auth/me")
    def get_current_user(user: User = Depends(current_user)) -> dict:
        return {"id": user.id, "username": user.username, "role": user.role, "department": user.department}

    @api.get("/api/v1/evaluations")
    def evaluations(user: User = Depends(admin_user)) -> dict:
        directory = Path(os.getenv("EVALUATION_REPORTS_DIR", Path(__file__).resolve().parents[1] / "reports"))
        return load_evaluation_dashboard(directory)

    @api.get("/api/v1/documents")
    def list_documents(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[dict]:
        active_ids = set(visible_version_ids(session, user.role, user.department))
        documents = session.scalars(
            select(Document).where(Document.deleted_at.is_(None)).order_by(Document.created_at.desc())
        ).all()
        return [
            {
                "id": document.id,
                "title": document.title,
                "department": document.department,
                "allowed_roles": document.allowed_roles,
                "active_version_id": document.active_version_id,
                "created_at": document.created_at,
            }
            for document in documents
            if user.role == "admin" or document.active_version_id in active_ids
        ]

    @api.get("/api/v1/documents/{document_id}/versions")
    def list_versions(
        document_id: str,
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> list[dict]:
        document = session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Document not found")
        versions = session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        ).all()
        jobs = session.scalars(select(IngestionJob).where(
            IngestionJob.version_id.in_([version.id for version in versions]),
            IngestionJob.kind == "index",
        )).all() if versions else []
        jobs_by_version = {job.version_id: job for job in jobs}
        return [
            {
                "id": version.id,
                "version_number": version.version_number,
                "filename": version.filename,
                "source_format": version.source_format,
                "effective_date": version.effective_date,
                "status": version.status,
                "created_at": version.created_at,
                "activated_at": version.activated_at,
                "job_id": jobs_by_version[version.id].id if version.id in jobs_by_version else None,
                "job_status": jobs_by_version[version.id].status if version.id in jobs_by_version else None,
                "job_error": jobs_by_version[version.id].error if version.id in jobs_by_version else None,
            }
            for version in versions
        ]

    @api.post("/api/v1/documents", status_code=202)
    def upload_document(
        request: Request,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(),
        title: str = Form(),
        department: str | None = Form(default=None),
        allowed_roles: str = Form(default="employee"),
        effective_date: date | None = Form(default=None),
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        try:
            version, job = stage_document(
                session, file.file, file.filename or "", title, request.app.state.storage_root,
                department=department or None,
                allowed_roles=[role.strip() for role in allowed_roles.split(",") if role.strip()],
                effective_date=effective_date,
            )
            result = {"document_id": version.document_id, "version_id": version.id, "job_id": job.id}
            session.add(AuditEvent(actor_id=user.id, action="document.upload", object_id=version.document_id, result="accepted"))
            session.commit()
            if request.app.state.inline_jobs:
                background_tasks.add_task(process_local_jobs, request.app)
            return result
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/v1/documents/{document_id}/versions", status_code=202)
    def upload_version(
        document_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(),
        effective_date: date | None = Form(default=None),
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        document = session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            version, job = stage_document(
                session, file.file, file.filename or "", document.title,
                request.app.state.storage_root, document_id=document_id,
                effective_date=effective_date,
            )
            result = {"document_id": document_id, "version_id": version.id, "job_id": job.id}
            session.add(AuditEvent(actor_id=user.id, action="version.upload", object_id=version.id, result="accepted"))
            session.commit()
            if request.app.state.inline_jobs:
                background_tasks.add_task(process_local_jobs, request.app)
            return result
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/v1/documents/{document_id}/versions/{version_id}/activate")
    def activate(
        document_id: str,
        version_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        try:
            activate_version(session, document_id, version_id)
            session.add(AuditEvent(actor_id=user.id, action="version.activate", object_id=version_id, result="succeeded"))
            session.commit()
            if request.app.state.inline_jobs:
                background_tasks.add_task(process_local_jobs, request.app)
        except LifecycleError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "active", "version_id": version_id}

    @api.delete("/api/v1/documents/{document_id}")
    def remove_document(
        document_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        try:
            delete_document(session, document_id)
            session.add(AuditEvent(actor_id=user.id, action="document.delete", object_id=document_id, result="succeeded"))
            session.commit()
            if request.app.state.inline_jobs:
                background_tasks.add_task(process_local_jobs, request.app)
        except LifecycleError as exc:
            session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"status": "deleted"}

    @api.get("/api/v1/documents/{document_id}/source")
    def get_source(
        document_id: str,
        version_id: str | None = None,
        user: User = Depends(current_user),
        session: Session = Depends(get_session),
    ):
        document = session.get(Document, document_id)
        allowed = visible_version_ids(session, user.role, user.department)
        if (
            document is None or document.active_version_id not in allowed
            or (version_id is not None and version_id != document.active_version_id)
        ):
            raise HTTPException(status_code=404, detail="Document not found")
        version = session.get(DocumentVersion, document.active_version_id)
        if version is None or not Path(version.storage_path).is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        return FileResponse(version.storage_path, filename=version.filename)

    @api.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, user: User = Depends(admin_user), session: Session = Depends(get_session)) -> dict:
        job = session.get(IngestionJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"id": job.id, "kind": job.kind, "status": job.status, "attempts": job.attempts, "error": job.error}

    @api.post("/api/v1/jobs/{job_id}/retry")
    def retry_failed_job(
        job_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict:
        try:
            job = retry_job(session, job_id)
            session.add(AuditEvent(actor_id=user.id, action="job.retry", object_id=job.id, result="accepted"))
            session.commit()
            if request.app.state.inline_jobs:
                background_tasks.add_task(process_local_jobs, request.app)
        except LifecycleError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"id": job.id, "status": job.status}

    @api.get("/api/v1/audit")
    def list_audit_events(user: User = Depends(admin_user), session: Session = Depends(get_session)) -> list[dict]:
        events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)).all()
        return [
            {"id": event.id, "actor_id": event.actor_id, "action": event.action,
             "object_id": event.object_id, "result": event.result, "created_at": event.created_at}
            for event in events
        ]

    @api.get("/api/v1/usage")
    def get_usage(
        request: Request,
        user: User = Depends(admin_user),
        session: Session = Depends(get_session),
    ) -> dict:
        day = now_utc().date().isoformat()
        budget = session.get(DailyTokenBudget, day)
        consumed = budget.consumed_tokens if budget else 0
        reserved = budget.reserved_tokens if budget else 0
        limit = request.app.state.daily_token_limit
        records = session.scalars(
            select(ChatRequestRecord).order_by(ChatRequestRecord.created_at.desc()).limit(50)
        ).all()
        return {
            "day": day,
            "limit": limit,
            "consumed_tokens": consumed,
            "reserved_tokens": reserved,
            "remaining_tokens": max(0, limit - consumed - reserved) if limit else None,
            "requests": [
                {
                    "id": record.id,
                    "actor_id": record.actor_id,
                    "status": record.status,
                    "model": record.model_name,
                    "retrieval_ms": record.retrieval_ms,
                    "generation_ms": record.generation_ms,
                    "total_ms": record.total_ms,
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "charged_tokens": record.charged_tokens,
                    "created_at": record.created_at,
                }
                for record in records
            ],
        }

    @api.post("/api/v1/search")
    def search(
        body: SearchRequest,
        request: Request,
        user: User = Depends(current_user),
        session: Session = Depends(get_session),
    ) -> list[dict]:
        version_ids = visible_version_ids(session, user.role, user.department)
        hits = find_hits(request, body.query, version_ids, body.limit)
        return [asdict(hit) for hit in still_visible(session, user, hits)]

    @api.post("/api/v1/chat")
    def chat(
        body: SearchRequest,
        request: Request,
        user: User = Depends(current_user),
        session: Session = Depends(get_session),
    ) -> dict:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        retrieval_ms = 0.0
        generation_ms = 0.0

        def respond(
            status: str, *, answer: str | None = None, citations: list | None = None,
            model_name: str | None = None, input_tokens: int | None = None, output_tokens: int | None = None,
        ) -> dict:
            total_ms = (time.perf_counter() - started) * 1000
            finish_chat_request(
                request.app.state.sessions, request_id, user.id, status,
                retrieval_ms=retrieval_ms, generation_ms=generation_ms, total_ms=total_ms,
                model_name=model_name, input_tokens=input_tokens, output_tokens=output_tokens,
            )
            result = {
                "request_id": request_id, "status": status, "answer": answer,
                "citations": citations or [],
                "retrieval_ms": round(retrieval_ms, 2),
                "generation_ms": round(generation_ms, 2),
                "total_ms": round(total_ms, 2),
            }
            if model_name is not None:
                result["model"] = model_name
            if input_tokens is not None:
                result["input_tokens"] = input_tokens
            if output_tokens is not None:
                result["output_tokens"] = output_tokens
            return result

        version_ids = visible_version_ids(session, user.role, user.department)
        sources = find_hits(request, body.query, version_ids, min(body.limit, 6))
        if not sources:
            retrieval_ms = (time.perf_counter() - started) * 1000
            return respond("insufficient_evidence")
        sources = still_visible(session, user, sources)
        retrieval_ms = (time.perf_counter() - started) * 1000
        if not sources:
            return respond("insufficient_evidence")
        if not request.app.state.llm_enabled or (
            not os.getenv("LLM_API_KEY") and answer_provider_factory is GlmAnswerProvider
        ):
            return respond("search_only", citations=[asdict(hit) for hit in sources])
        reservation = estimate_token_reservation(body.query, sources)
        if not reserve_tokens(
            request.app.state.sessions, request_id, user.id, reservation, request.app.state.daily_token_limit
        ):
            visible_sources = still_visible(session, user, sources)
            if not visible_sources:
                return respond("insufficient_evidence")
            return respond("quota_exceeded", citations=[asdict(hit) for hit in visible_sources])
        generation_started = time.perf_counter()
        try:
            if request.app.state.answer_provider is None:
                request.app.state.answer_provider = request.app.state.answer_provider_factory()
        except Exception:
            generation_ms = (time.perf_counter() - generation_started) * 1000
            settle_tokens(request.app.state.sessions, request_id, 0)
            visible_sources = still_visible(session, user, sources)
            if not visible_sources:
                return respond("insufficient_evidence")
            return respond("model_unavailable", citations=[asdict(hit) for hit in visible_sources])
        model_name = request.app.state.answer_provider.model_name
        try:
            generated = request.app.state.answer_provider.answer(body.query, sources)
        except Exception:
            generation_ms = (time.perf_counter() - generation_started) * 1000
            settle_tokens(request.app.state.sessions, request_id, None)
            visible_sources = still_visible(session, user, sources)
            if not visible_sources:
                return respond("insufficient_evidence", model_name=model_name)
            return respond("model_unavailable", citations=[asdict(hit) for hit in visible_sources], model_name=model_name)
        generation_ms = (time.perf_counter() - generation_started) * 1000
        actual_tokens = (
            generated.input_tokens + generated.output_tokens
            if generated.input_tokens is not None and generated.output_tokens is not None else None
        )
        settle_tokens(request.app.state.sessions, request_id, actual_tokens)
        try:
            cited = cited_sources(generated.text, sources)
        except ValueError:
            return respond(
                "invalid_citation", model_name=model_name,
                input_tokens=generated.input_tokens, output_tokens=generated.output_tokens,
            )
        visible_cited = still_visible(session, user, cited)
        if not cited or len(visible_cited) != len(cited):
            return respond(
                "insufficient_evidence", model_name=model_name,
                input_tokens=generated.input_tokens, output_tokens=generated.output_tokens,
            )
        return respond(
            "answered", answer=generated.text, citations=[asdict(hit) for hit in visible_cited],
            model_name=model_name, input_tokens=generated.input_tokens, output_tokens=generated.output_tokens,
        )

    return api
