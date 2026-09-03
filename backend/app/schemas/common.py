from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    detail: str


class CargaMasivaResultado(BaseModel):
    """Shared result shape for every bulk-upload/upsert endpoint
    (afiliados, convenios, inventario) — aggregate counts PLUS a
    per-row reason for every invalid row, so a real error can be found
    and fixed in the source file instead of just knowing "N filas
    fallaron"."""

    detail: str
    creados: int = 0
    # A row only counts as `actualizados` if at least one field's value
    # actually differs from what's already in the database — never just
    # because the row matched an existing record. A matched row where
    # every provided value is identical to what's already there counts as
    # `omitidos` instead (see below), so re-uploading the same file (or
    # one where only 1 row genuinely changed) reports that honestly
    # instead of claiming the whole file was "updated".
    actualizados: int = 0
    # Rows that were valid but intentionally skipped without error — e.g.
    # a duplicate inventory `codigo` (already exists, nothing to update),
    # or an afiliado/convenio row that matched an existing record with no
    # actual field differences. Kept separate from `invalidos` because
    # it isn't a data problem to fix in the file, unlike everything
    # listed in `errores`.
    omitidos: int = 0
    invalidos: int = 0
    errores: list[str] = []
    # Per-row "field X changed from A to B" notes for every row counted
    # in `actualizados` — lets an admin verify EXACTLY what a re-upload
    # touched, rather than just trusting an aggregate count.
    cambios: list[str] = []


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
