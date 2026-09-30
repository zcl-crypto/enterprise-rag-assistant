from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rag_app.db import Base, ChatRequestRecord, DailyTokenBudget, User, now_utc
from rag_app.quota import finish_chat_request, reconcile_stale_reservations, reserve_tokens, settle_tokens


def setup_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'quota.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        user = User(username="admin", password_hash="hash", role="admin", is_active=True)
        session.add(user)
        session.flush()
        user_id = user.id
    return engine, sessions, user_id


def test_reserve_settle_and_request_trace(tmp_path: Path) -> None:
    engine, sessions, actor_id = setup_database(tmp_path)
    day = date(2026, 1, 2)
    assert reserve_tokens(sessions, "request-1", actor_id, 80, 100, day=day)
    assert not reserve_tokens(sessions, "request-2", actor_id, 30, 100, day=day)
    with Session(engine) as session:
        budget = session.get(DailyTokenBudget, day.isoformat())
        assert (budget.consumed_tokens, budget.reserved_tokens) == (0, 80)
    assert settle_tokens(sessions, "request-1", 20) == 20
    finish_chat_request(
        sessions, "request-1", actor_id, "answered", retrieval_ms=10.123,
        generation_ms=50.456, total_ms=60.579, model_name="test-model", input_tokens=15, output_tokens=5,
    )
    assert reserve_tokens(sessions, "request-2", actor_id, 30, 100, day=day)
    assert settle_tokens(sessions, "request-2", None) == 30
    with Session(engine) as session:
        budget = session.get(DailyTokenBudget, day.isoformat())
        record = session.get(ChatRequestRecord, "request-1")
        assert (budget.consumed_tokens, budget.reserved_tokens) == (50, 0)
        assert record.status == "answered"
        assert record.budget_day == day.isoformat()
        assert record.retrieval_ms == 10.12
        assert record.charged_tokens == 20
        assert not record.reservation_active
    with pytest.raises(ValueError, match="not active"):
        settle_tokens(sessions, "request-1", 20)
    engine.dispose()


def test_concurrent_reservations_cannot_exceed_daily_limit(tmp_path: Path) -> None:
    engine, sessions, actor_id = setup_database(tmp_path)
    barrier = Barrier(2)

    def reserve(request_id: str) -> bool:
        barrier.wait()
        return reserve_tokens(sessions, request_id, actor_id, 70, 100)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["concurrent-1", "concurrent-2"]))
    assert sorted(results) == [False, True]
    with Session(engine) as session:
        budget = session.get(DailyTokenBudget, now_utc().date().isoformat())
        assert budget.reserved_tokens == 70
    engine.dispose()


def test_no_generation_trace_does_not_consume_budget(tmp_path: Path) -> None:
    engine, sessions, actor_id = setup_database(tmp_path)
    finish_chat_request(
        sessions, "search-only", actor_id, "search_only", retrieval_ms=8,
        generation_ms=0, total_ms=8,
    )
    with Session(engine) as session:
        record = session.get(ChatRequestRecord, "search-only")
        assert record.status == "search_only"
        assert record.charged_tokens == 0
        assert record.reserved_tokens == 0
        assert record.finished_at is not None
    engine.dispose()


def test_stale_reservation_is_charged_once_without_touching_live_request(tmp_path: Path) -> None:
    engine, sessions, actor_id = setup_database(tmp_path)
    assert reserve_tokens(sessions, "interrupted", actor_id, 80, 100)
    assert reserve_tokens(sessions, "live", actor_id, 10, 100)
    with sessions.begin() as session:
        session.get(ChatRequestRecord, "interrupted").created_at = now_utc() - timedelta(hours=1)

    assert reconcile_stale_reservations(sessions) == 1
    assert reconcile_stale_reservations(sessions) == 0
    with Session(engine) as session:
        budget = session.get(DailyTokenBudget, now_utc().date().isoformat())
        interrupted = session.get(ChatRequestRecord, "interrupted")
        live = session.get(ChatRequestRecord, "live")
        assert (budget.consumed_tokens, budget.reserved_tokens) == (80, 10)
        assert interrupted.status == "usage_unconfirmed"
        assert interrupted.charged_tokens == 80
        assert interrupted.finished_at is not None
        assert not interrupted.reservation_active
        assert live.status == "reserved" and live.reservation_active
    assert not reserve_tokens(sessions, "over-limit", actor_id, 15, 100)
    with pytest.raises(ValueError, match="not active"):
        settle_tokens(sessions, "interrupted", 2)
    engine.dispose()


def test_reservation_recovery_runs_before_next_budget_check(tmp_path: Path) -> None:
    engine, sessions, actor_id = setup_database(tmp_path)
    assert reserve_tokens(sessions, "interrupted", actor_id, 80, 100)
    with sessions.begin() as session:
        session.get(ChatRequestRecord, "interrupted").created_at = now_utc() - timedelta(hours=1)

    assert not reserve_tokens(sessions, "next", actor_id, 30, 100)
    with Session(engine) as session:
        budget = session.get(DailyTokenBudget, now_utc().date().isoformat())
        assert (budget.consumed_tokens, budget.reserved_tokens) == (80, 0)
        assert session.get(ChatRequestRecord, "interrupted").status == "usage_unconfirmed"
    engine.dispose()
