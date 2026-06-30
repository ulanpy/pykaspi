from __future__ import annotations

from typing import Any


class PykaspiError(Exception):
    """Base pykaspi exception."""


class KaspiApiError(PykaspiError):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class KaspiAuthError(KaspiApiError):
    """Raised when the Kaspi auth/session flow is rejected."""


class KaspiReauthRequiredError(KaspiAuthError):
    """Raised when SignInLite refresh cannot recover the session and SMS auth is required."""
