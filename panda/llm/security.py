"""Security layer stubs (encryption/decryption hooks)."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any


class BaseSecurityLayer(ABC):
    """Security contract."""

    @abstractmethod
    def encrypt(self, data: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def decrypt(self, token: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def sanitize(self, data: Any) -> Any:
        raise NotImplementedError


class SecurityLayer(BaseSecurityLayer):
    """Placeholder encryption/decryption. Swap with real crypto in production."""

    def encrypt(self, data: str) -> str:
        # TODO: Replace with proper encryption (e.g., AES/GCM) and key management.
        return base64.b64encode(data.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            return base64.b64decode(token.encode("utf-8")).decode("utf-8")
        except Exception as exc:  # pragma: no cover - simple guard
            raise ValueError("Invalid encrypted payload") from exc

    def sanitize(self, data: Any) -> Any:
        # TODO: Add PII scrubbing / policy enforcement.
        return data


__all__ = ["BaseSecurityLayer", "SecurityLayer"]

