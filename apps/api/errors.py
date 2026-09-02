from __future__ import annotations


class APIError(Exception):
    """Base exception for expected API failures."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RuntimeControlError(APIError):
    """Raised when a runtime control operation fails."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 500,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
        )