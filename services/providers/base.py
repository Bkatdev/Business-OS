"""Provider contracts for Business OS external actions."""
from __future__ import annotations

from dataclasses import dataclass


class ProviderUnavailable(RuntimeError):
    """Raised when an action has no deliberately configured provider."""


@dataclass(frozen=True)
class ProviderResult:
    # outcome: CONFIRMED, ACCEPTED, FAILED, or UNKNOWN
    outcome: str
    detail: str
    external_id: str = ""
    retryable: bool = False
    error_class: str = ""


class ProviderAdapter:
    name = "base"

    def execute(self, *, action, payload) -> ProviderResult:
        raise NotImplementedError
