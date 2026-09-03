"""
Safe helpers for anything driven by client-supplied query parameters.

The rule: a client may choose *which* allowed field to sort/filter by,
never supply an arbitrary column name or SQL fragment. Every router that
accepts `sort_by`/`order` validates against an explicit allowlist here.
"""
from fastapi import HTTPException, status


def resolve_sort_column(model, sort_by: str | None, allowed_fields: set[str], default: str):
    """Returns a mapped column object for a validated, allowlisted field
    name — never builds a query from a raw string the client controls."""
    field = sort_by if sort_by in allowed_fields else default
    return getattr(model, field)


def clamp_pagination(page: int, page_size: int, max_page_size: int = 100) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), max_page_size)
    return page, page_size


def require_allowed_value(value: str, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor no permitido para '{field_name}'.",
        )
    return value
