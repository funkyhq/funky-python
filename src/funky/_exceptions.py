from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class FunkyError(Exception):
    """Base exception for all Funky SDK errors."""


class APIConnectionError(FunkyError):
    """The SDK could not connect to the Funky API."""


class APITimeoutError(APIConnectionError):
    """A request or local wait operation timed out."""


class APIStatusError(FunkyError):
    """The Funky API returned an unsuccessful HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_type: str | None = None,
        code: str | None = None,
        request_id: str | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.request_id = request_id
        self.headers = dict(headers or {})
        self.body = body

    def __str__(self) -> str:
        details = [f"status={self.status_code}"]
        if self.code:
            details.append(f"code={self.code}")
        if self.request_id:
            details.append(f"request_id={self.request_id}")
        return f"{self.message} ({', '.join(details)})"


class BadRequestError(APIStatusError):
    pass


class AuthenticationError(APIStatusError):
    pass


class PermissionDeniedError(APIStatusError):
    pass


class NotFoundError(APIStatusError):
    pass


class ConflictError(APIStatusError):
    pass


class RateLimitError(APIStatusError):
    pass


class InternalServerError(APIStatusError):
    pass


_STATUS_EXCEPTIONS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    500: InternalServerError,
    502: InternalServerError,
    503: InternalServerError,
    504: InternalServerError,
}


def status_error(
    status_code: int,
    *,
    payload: Any,
    headers: Mapping[str, str],
) -> APIStatusError:
    envelope = payload if isinstance(payload, dict) else {}
    raw_error = envelope.get("error")
    error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
    message = error.get("message") or f"Funky API request failed with status {status_code}"
    request_id = envelope.get("request_id") or headers.get("request-id")
    exception_type = _STATUS_EXCEPTIONS.get(status_code, APIStatusError)
    return exception_type(
        str(message),
        status_code=status_code,
        error_type=error.get("type"),
        code=error.get("code"),
        request_id=request_id,
        headers=headers,
        body=payload,
    )
