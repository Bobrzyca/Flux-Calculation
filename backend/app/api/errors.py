"""Structured API errors the frontend can branch on.

Every error body is ``{"detail": {"code", "message", "field"?}}`` so the frontend
client can rebuild its ``ApiError { code, field }`` and keep highlighting the
right form field.
"""

from fastapi import HTTPException


def api_error(
    status_code: int, code: str, message: str, field: str | None = None
) -> HTTPException:
    """Build an HTTPException whose detail carries a stable code (+ optional field)."""
    detail: dict[str, str] = {"code": code, "message": message}
    if field is not None:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)
