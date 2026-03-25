from __future__ import annotations


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class ValidationError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 400)


class NotFoundError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 404)


class ConflictError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 409)


class PermissionDeniedError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 403)


class ExternalDependencyError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 502)


class TransientDependencyError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503, retryable=True)
