from __future__ import annotations

from sqlalchemy.orm import Session

from cvm_platform.application.service import PlatformService
from cvm_platform.infrastructure.adapters import MockResumeSourceAdapter, StubLLMAdapter
from cvm_platform.infrastructure.db import get_session


def service_dependency():
    for session in get_session():
        yield PlatformService(session=session, llm=StubLLMAdapter(), resume_source=MockResumeSourceAdapter())
