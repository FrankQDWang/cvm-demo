from __future__ import annotations

from cvm_platform.infrastructure.db import get_session
from cvm_platform.infrastructure.service_factory import build_platform_service
from cvm_platform.settings.config import settings


def service_dependency():
    for session in get_session():
        yield build_platform_service(session, settings)
