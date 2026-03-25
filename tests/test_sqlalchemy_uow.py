from __future__ import annotations

from datetime import UTC, datetime

from cvm_platform.application.dto import CandidateRecord
from cvm_platform.infrastructure.models import CaseCandidateModel
from cvm_platform.infrastructure.sqlalchemy_uow import _save_record


class FakeSession:
    def __init__(self) -> None:
        self.new: list[object] = []
        self._persisted: dict[tuple[type[object], object], object] = {}

    def get(self, model_type: type[object], record_id: object) -> object | None:
        return self._persisted.get((model_type, record_id))

    def add(self, model: object) -> None:
        self.new.append(model)


def test_save_record_reuses_pending_candidate_model() -> None:
    session = FakeSession()
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

    _save_record(session, CaseCandidateModel, candidate)
    candidate.latest_resume_snapshot_id = "snap_test"
    candidate.updated_at = datetime.now(UTC)
    _save_record(session, CaseCandidateModel, candidate)

    assert len(session.new) == 1
    pending = session.new[0]
    assert isinstance(pending, CaseCandidateModel)
    assert pending.id == "cand_test"
    assert pending.latest_resume_snapshot_id == "snap_test"
