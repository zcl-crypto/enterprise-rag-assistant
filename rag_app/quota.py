from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from rag_app.db import ChatRequestRecord, DailyTokenBudget, now_utc
from rag_app.generation import MAX_GENERATION_ATTEMPTS, MAX_OUTPUT_TOKENS, build_messages
from rag_app.vector_index import SearchHit


STALE_RESERVATION_AFTER = timedelta(minutes=30)


def estimate_token_reservation(question: str, sources: Sequence[SearchHit]) -> int:
    prompt_bytes = max(
        sum(len(message["content"].encode("utf-8")) for message in build_messages(
            question, sources, citation_retry=mode == "citation", refusal_retry=mode == "refusal",
        ))
        for mode in (None, "citation", "refusal")
    )
    return MAX_GENERATION_ATTEMPTS * (prompt_bytes * 2 + MAX_OUTPUT_TOKENS + 512)


def reconcile_stale_reservations(sessions: sessionmaker) -> int:
    cutoff = now_utc() - STALE_RESERVATION_AFTER
    reconciled = 0
    with sessions() as session:
        ids = session.scalars(select(ChatRequestRecord.id).where(
            ChatRequestRecord.reservation_active.is_(True),
            ChatRequestRecord.created_at <= cutoff,
        ).order_by(ChatRequestRecord.created_at, ChatRequestRecord.id)).all()
    for request_id in ids:
        with sessions.begin() as session:
            record = session.scalar(select(ChatRequestRecord).where(
                ChatRequestRecord.id == request_id,
                ChatRequestRecord.reservation_active.is_(True),
                ChatRequestRecord.created_at <= cutoff,
            ).with_for_update())
            if record is None:
                continue
            budget = session.scalar(select(DailyTokenBudget).where(
                DailyTokenBudget.day == record.budget_day,
            ).with_for_update())
            if budget is None or budget.reserved_tokens < record.reserved_tokens:
                raise ValueError("Token reservation budget is inconsistent")
            budget.reserved_tokens -= record.reserved_tokens
            budget.consumed_tokens += record.reserved_tokens
            record.charged_tokens = record.reserved_tokens
            record.reservation_active = False
            record.status = "usage_unconfirmed"
            record.finished_at = now_utc()
            reconciled += 1
    return reconciled


def reserve_tokens(
    sessions: sessionmaker, request_id: str, actor_id: str, amount: int, daily_limit: int,
    *, day: date | None = None,
) -> bool:
    if amount <= 0 or daily_limit < 0:
        raise ValueError("Invalid token reservation or daily limit")
    reconcile_stale_reservations(sessions)
    day_key = (day or now_utc().date()).isoformat()
    with sessions.begin() as session:
        dialect = session.bind.dialect.name
        if dialect == "postgresql":
            insert = postgres_insert(DailyTokenBudget)
        elif dialect == "sqlite":
            insert = sqlite_insert(DailyTokenBudget)
        else:
            raise ValueError(f"Unsupported quota database: {dialect}")
        session.execute(insert.values(day=day_key, consumed_tokens=0, reserved_tokens=0).on_conflict_do_nothing(
            index_elements=[DailyTokenBudget.day]
        ))
        budget = session.scalar(select(DailyTokenBudget).where(DailyTokenBudget.day == day_key).with_for_update())
        if daily_limit and budget.consumed_tokens + budget.reserved_tokens + amount > daily_limit:
            return False
        budget.reserved_tokens += amount
        session.add(ChatRequestRecord(
            id=request_id, actor_id=actor_id, status="reserved", reserved_tokens=amount,
            reservation_active=True, budget_day=day_key,
        ))
    return True


def settle_tokens(sessions: sessionmaker, request_id: str, actual_tokens: int | None) -> int:
    if actual_tokens is not None and actual_tokens < 0:
        raise ValueError("Token usage must be nonnegative")
    with sessions.begin() as session:
        record = session.scalar(select(ChatRequestRecord).where(ChatRequestRecord.id == request_id).with_for_update())
        if record is None or not record.reservation_active:
            raise ValueError("Token reservation is not active")
        budget = session.scalar(select(DailyTokenBudget).where(DailyTokenBudget.day == record.budget_day).with_for_update())
        charged = record.reserved_tokens if actual_tokens is None else actual_tokens
        budget.reserved_tokens -= record.reserved_tokens
        budget.consumed_tokens += charged
        record.charged_tokens = charged
        record.reservation_active = False
        record.status = "settled"
    return charged


def finish_chat_request(
    sessions: sessionmaker, request_id: str, actor_id: str, status: str,
    *, retrieval_ms: float, generation_ms: float, total_ms: float,
    model_name: str | None = None, input_tokens: int | None = None, output_tokens: int | None = None,
) -> None:
    with sessions.begin() as session:
        record = session.get(ChatRequestRecord, request_id)
        if record is None:
            record = ChatRequestRecord(id=request_id, actor_id=actor_id, status=status)
            session.add(record)
        if record.reservation_active:
            raise ValueError("Active token reservation must be settled before request completion")
        record.status = status
        record.model_name = model_name
        record.retrieval_ms = round(retrieval_ms, 2)
        record.generation_ms = round(generation_ms, 2)
        record.total_ms = round(total_ms, 2)
        record.input_tokens = input_tokens
        record.output_tokens = output_tokens
        record.finished_at = now_utc()
