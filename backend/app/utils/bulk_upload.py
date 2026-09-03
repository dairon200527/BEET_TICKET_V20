"""
Shared CSV/XLSX row-parsing for bulk-upload endpoints (afiliados,
convenios, inventario). This module only turns uploaded bytes into a
list of plain dicts keyed by a NORMALIZED header name (see
`normalize_header` below) — every field value is still just a string at
this point. All real validation (required fields, types, business
rules, per-tenant duplicate checks) happens in the calling router via
the existing Pydantic schemas; nothing here is trusted as-is.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata

from fastapi import HTTPException, status
from pydantic import ValidationError


def normalize_header(raw: str) -> str:
    """Canonicalizes a column header so a human-typed one (accents,
    mixed case, spaces instead of underscores...) matches the same
    snake_case key the routers look up via `row.get("cupo_total")` etc.

    'Cupo total' / 'CUPO TOTAL' / 'cupo-total' / 'Cupo  Total' all become
    'cupo_total'; 'Teléfono' becomes 'telefono'. Before this normalization
    existed, any header that didn't match the exact expected string was
    silently ignored — the column's value was just never read, with no
    error — which is how a real Excel with human-readable headers (e.g.
    'Cupo total') lost its cupo_total/telefono columns without any
    visible failure. See `require_columns` for the other half of the
    fix: a column still missing after this normalization is now a hard,
    explicit rejection instead of a silent one."""
    text = unicodedata.normalize("NFKD", raw or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))  # strip accents
    text = text.strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)  # spaces/hyphens -> underscore
    text = re.sub(r"_+", "_", text).strip("_")  # collapse repeats, trim
    return text


def require_columns(headers: list[str], required: list[str]) -> None:
    """Raises a clear 400 if any required (already-normalized, snake_case)
    column is missing from the file's (already-normalized) headers —
    called once per upload, before any row is processed, so a malformed
    file never gets silently, partially processed with missing columns
    defaulting to empty/zero."""
    faltantes = [c for c in required if c not in headers]
    if faltantes:
        etiquetas = ", ".join(f"'{c}'" for c in faltantes)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falta la columna obligatoria {etiquetas}." if len(faltantes) == 1 else f"Faltan las columnas obligatorias: {etiquetas}.",
        )


def parse_rows(filename: str, content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Returns `(headers, rows)` — `headers` is the file's normalized
    column list (present even for a file with zero data rows, which is
    exactly when `require_columns` still needs to check something)."""
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        return _parse_csv(content)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return _parse_xlsx(content)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de archivo no soportado.")


def _parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = [normalize_header(h) for h in (reader.fieldnames or [])]
    rows = [{normalize_header(k or ""): (v or "").strip() for k, v in row.items()} for row in reader]
    return headers, rows


_FALSE_TOKENS = {"false", "0", "no", "inactivo"}


def parse_bool(raw: str | None, default: bool = True) -> bool:
    """Flexible boolean parsing for a bulk-upload column — anything that
    isn't one of the recognized "false" tokens (false/0/no/inactivo,
    case-insensitive) is treated as true. Blank means `default`."""
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in _FALSE_TOKENS


def parse_bool_or_none(raw: str | None) -> bool | None:
    """Same flexible values as `parse_bool`, but a blank cell means "not
    provided" (`None`) rather than any particular default — used by
    upsert flows where a blank `estado` column must leave an EXISTING
    row's estado untouched, not silently reset it to a default."""
    if raw is None or raw.strip() == "":
        return None
    return parse_bool(raw)


def summarize_validation_error(exc: ValidationError) -> str:
    """Turns a Pydantic row-validation failure into one short, human
    (Spanish) reason for the per-row error report every bulk-upload
    endpoint returns — e.g. 'correo: value is not a valid email address'
    becomes part of 'Fila 5: correo inválido; cupo_total inválido'.

    A `raise ValueError("...")` from a custom `@field_validator`/
    `@model_validator` (a business rule, e.g. "El precio BEET no puede
    ser mayor al precio público.") keeps its own specific message instead
    of being flattened into the generic 'campo inválido o vacío' — that
    flattening used to throw away the actual reason for exactly the
    validators that most need to explain themselves."""
    partes = []
    for err in exc.errors():
        if err["type"] == "value_error":
            # Pydantic prefixes custom ValueError messages with
            # "Value error, " in the rendered `msg` — strip it back off.
            partes.append(str(err["msg"]).removeprefix("Value error, "))
        else:
            campo = str(err["loc"][-1]) if err["loc"] else "valor"
            partes.append(f"{campo} inválido o vacío")
    return "; ".join(dict.fromkeys(partes))  # de-duplicate, keep order


def _parse_xlsx(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El soporte para archivos .xlsx no está disponible en este servidor.",
        )

    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active
    rows_iter = worksheet.iter_rows(values_only=True)
    try:
        headers = [normalize_header(str(h or "")) for h in next(rows_iter)]
    except StopIteration:
        return [], []

    rows: list[dict[str, str]] = []
    for values in rows_iter:
        if values is None or all(v is None for v in values):
            continue
        row = {headers[i]: ("" if v is None else str(v).strip()) for i, v in enumerate(values) if i < len(headers)}
        rows.append(row)
    return headers, rows
