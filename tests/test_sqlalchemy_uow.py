from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from cvm_platform.application.dto import CandidateRecord
from cvm_platform.infrastructure.db import Base
from cvm_platform.infrastructure.models import CaseCandidateModel
from cvm_platform.infrastructure.sqlalchemy_uow import _save_record


def test_save_record_reuses_pending_candidate_model() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    timestamp = datetime.now(UTC)
    candidate = CandidateRecord(
        id="cand_test",
        case_id="case_test",
        external_identity_id="cts_001",
        latest_resume_snapshot_id=None,
        latest_verdict=None,
        dedupe_status="unique",
        name="Alice",
        title="Backend Engineer",
        company="Example Corp",
        location="Shanghai",
        summary="Python",
        email="alice@example.com",
        phone="13800000000",
        created_at=timestamp,
        updated_at=timestamp,
    )

    with Session(engine) as session:
        _save_record(session, CaseCandidateModel, candidate)
        candidate.latest_resume_snapshot_id = "snap_test"
        candidate.updated_at = datetime.now(UTC)
        _save_record(session, CaseCandidateModel, candidate)
        session.commit()

        rows = session.scalars(select(CaseCandidateModel)).all()

    engine.dispose()

    assert len(rows) == 1
    assert rows[0].id == "cand_test"
    assert rows[0].latest_resume_snapshot_id == "snap_test"
