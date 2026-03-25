from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from cvm_platform.application.service import PlatformService
from cvm_platform.infrastructure.db import get_session
from cvm_platform.infrastructure.service_factory import build_platform_service
from cvm_platform.settings.config import settings


def service_dependency() -> Iterator[PlatformService]:
    for session in get_session():
        assert isinstance(session, Session)
        yield build_platform_service(session, settings)
