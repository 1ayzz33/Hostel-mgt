"""Domain errors that map cleanly onto HTTP responses."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        payload = {"error": self.message}
        if self.details:
            payload["details"] = self.details
        return payload
