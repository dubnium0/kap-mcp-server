from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class KapError(Exception):
    code: str
    message: str
    retryable: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
        }
        if self.context:
            result["error"]["context"] = self.context
        return result


VALIDATION_ERROR = "validation_error"
ENTITY_NOT_FOUND = "entity_not_found"
ENTITY_AMBIGUOUS = "entity_ambiguous"
DISCLOSURE_NOT_FOUND = "disclosure_not_found"
ATTACHMENT_NOT_FOUND = "attachment_not_found"
UPSTREAM_CHANGED = "upstream_changed"
UPSTREAM_UNAVAILABLE = "upstream_unavailable"
UNSUPPORTED_DOCUMENT = "unsupported_document"
PARSE_FAILED = "parse_failed"
VALIDATION_FAILED = "validation_failed"
UNSAFE_PATH = "unsafe_path"
FILE_EXISTS = "file_exists"
