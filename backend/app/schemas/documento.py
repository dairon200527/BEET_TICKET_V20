from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import EstadoDocumento


class DocumentoOut(BaseModel):
    """Admin-facing, read-only. NOTE: unlike an earlier design assumption,
    this table has no `afiliado_id`/`valor`/`cuotas` columns — those are
    derived by the router by joining through `transaccion_id`, not read
    directly off this ORM object."""

    id: int
    transaccion_id: int
    documento_storage_path: str
    firma_storage_path: str | None
    estado: EstadoDocumento
    fecha_generacion: datetime
    fecha_firma: datetime | None

    model_config = {"from_attributes": True}


class DocumentoMioOut(BaseModel):
    """The affiliate's own view of one of their debt-assumption
    documents (`GET /api/documentos/me`) — `valor`/`numero_cuotas` come
    from a join through `transacciones`, exactly like `DocumentoLegalItem`
    does for the admin dispute-search view, since this table itself has
    neither column."""

    id: int
    transaccion_id: int
    valor: Decimal
    numero_cuotas: int | None
    estado: EstadoDocumento
    fecha_generacion: datetime
    fecha_firma: datetime | None


class AfiliadoLegalOut(BaseModel):
    """Minimal identity, returned alongside a documentos-legales search
    result so the admin can visually confirm they found the right
    person — never the filter itself (see routers/documentos.py:
    `documento` is the only real filter; two different people never
    share one within the same cooperativa)."""

    id: int
    nombres: str
    apellidos: str
    documento: str
    nombre_coincide: bool | None = None


class DocumentoLegalItem(BaseModel):
    id: int
    transaccion_id: int
    convenio_nombre: str
    valor: Decimal
    numero_cuotas: int | None
    fecha_generacion: datetime
    fecha_firma: datetime | None
    estado: EstadoDocumento


class BusquedaDocumentosLegalesOut(BaseModel):
    afiliado: AfiliadoLegalOut | None
    documentos: list[DocumentoLegalItem]
