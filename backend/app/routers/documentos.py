"""
Debt-assumption documents (`/api/documentos`) — admin, mostly READ-ONLY.

NOTE: unlike an earlier design assumption, `documentos_asuncion_deuda` has
no `afiliado_id` column — cooperativa scoping is derived via a join
through `transacciones` -> `afiliados`.

`/legales/buscar` and `/{documento_id}/descarga` exist to support a
dispute ("the affiliate says they never accepted that commitment"): an
admin looks up every debt-assumption document a given affiliate has
signed, by `documento` (cédula) — the only real filter, since two
different people never share one within a cooperativa — and can download
the real, previously-generated PDF proof. Every search that actually
surfaces documents is written to `logs_auditoria`, since this is
sensitive legal evidence and who looked it up (and when) must be
traceable.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user, get_current_affiliate, resolve_cooperativa_scope
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.documento_asuncion_deuda import DocumentoAsuncionDeuda
from app.models.transaccion import Transaccion
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.common import Page
from app.schemas.documento import (
    AfiliadoLegalOut,
    BusquedaDocumentosLegalesOut,
    DocumentoLegalItem,
    DocumentoMioOut,
    DocumentoOut,
)
from app.services import audit_service, storage_service

router = APIRouter(prefix="/api/documentos", tags=["documentos"])


@router.get("/me", response_model=Page[DocumentoMioOut])
def mis_documentos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> Page[DocumentoMioOut]:
    """Every debt-assumption document belonging to the authenticated
    affiliate's OWN transactions — this is the endpoint the portal's
    "Mis documentos"/`DocumentDetail` screens were already built against
    (see frontend/src/services/documentosService.js), which previously
    had no backend route to call at all."""
    stmt = (
        select(DocumentoAsuncionDeuda, Transaccion.total, Transaccion.numero_cuotas)
        .join(Transaccion, Transaccion.id == DocumentoAsuncionDeuda.transaccion_id)
        .where(Transaccion.afiliado_id == afiliado.id)
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(DocumentoAsuncionDeuda.fecha_generacion.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .all()
    )
    items = [
        DocumentoMioOut(
            id=doc.id, transaccion_id=doc.transaccion_id, valor=valor, numero_cuotas=numero_cuotas,
            estado=doc.estado, fecha_generacion=doc.fecha_generacion, fecha_firma=doc.fecha_firma,
        )
        for doc, valor, numero_cuotas in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/me/{documento_id}/descarga")
def descargar_mi_documento(
    documento_id: int,
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> Response:
    """Streams the real PDF bytes directly — same pattern as
    `routers/tickets.py`'s `/me/{unidad_id}/descarga` — never a JSON
    envelope with a URL, so the frontend can hand the response straight
    to the browser as a Blob."""
    row = db.execute(
        select(DocumentoAsuncionDeuda)
        .join(Transaccion, Transaccion.id == DocumentoAsuncionDeuda.transaccion_id)
        .where(DocumentoAsuncionDeuda.id == documento_id, Transaccion.afiliado_id == afiliado.id)
    ).scalar_one_or_none()
    if row is None:
        # Hides both "doesn't exist" and "belongs to someone else" alike.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pdf_bytes = storage_service.download_bytes(row.documento_storage_path)
    if pdf_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo del documento no está disponible.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="documento-asuncion-deuda-{documento_id}.pdf"'},
    )


@router.get("", response_model=Page[DocumentoOut])
def listar(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[DocumentoOut]:
    stmt = (
        select(DocumentoAsuncionDeuda)
        .join(Transaccion, Transaccion.id == DocumentoAsuncionDeuda.transaccion_id)
        .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
        .where(Afiliado.cooperativa_id == cooperativa_id)
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(DocumentoAsuncionDeuda.fecha_generacion.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[DocumentoOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/legales/buscar", response_model=BusquedaDocumentosLegalesOut)
def buscar_documentos_legales(
    documento: str = Query(..., min_length=1, max_length=30),
    nombres: str | None = Query(default=None, max_length=200),
    admin: UsuarioAdmin = Depends(get_current_admin_user),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> BusquedaDocumentosLegalesOut:
    """`documento` is the only filter that actually restricts the query —
    `nombres`, if sent, is only compared against the match for a
    `nombre_coincide` flag the admin can use to visually confirm they
    found the right person; it never excludes a real match on a typo.

    An unmatched `documento` returns an empty result (never a 404) so the
    response can't be used to fingerprint whether that document number
    exists in a DIFFERENT cooperativa than the one in scope."""
    afiliado = db.execute(
        select(Afiliado).where(Afiliado.documento == documento, Afiliado.cooperativa_id == cooperativa_id)
    ).scalar_one_or_none()

    if afiliado is None:
        return BusquedaDocumentosLegalesOut(afiliado=None, documentos=[])

    rows = db.execute(
        select(DocumentoAsuncionDeuda, Transaccion, Convenio)
        .join(Transaccion, Transaccion.id == DocumentoAsuncionDeuda.transaccion_id)
        .join(Convenio, Convenio.id == Transaccion.convenio_id)
        .where(Transaccion.afiliado_id == afiliado.id)
        .order_by(DocumentoAsuncionDeuda.fecha_generacion.desc())
    ).all()

    documentos = [
        DocumentoLegalItem(
            id=doc.id,
            transaccion_id=transaccion.id,
            convenio_nombre=convenio.nombre,
            valor=transaccion.total,
            numero_cuotas=transaccion.numero_cuotas,
            fecha_generacion=doc.fecha_generacion,
            fecha_firma=doc.fecha_firma,
            estado=doc.estado,
        )
        for doc, transaccion, convenio in rows
    ]

    nombre_coincide = None
    if nombres is not None and nombres.strip():
        nombre_completo = f"{afiliado.nombres} {afiliado.apellidos}".strip().casefold()
        nombre_coincide = nombres.strip().casefold() in nombre_completo or nombre_completo in nombres.strip().casefold()

    if documentos:
        audit_service.record(
            db, usuario_admin_id=admin.id,
            accion="documentos_legales_consultados", tabla_afectada="documentos_asuncion_deuda", registro_id=afiliado.id,
            detalles={"documento": documento, "cantidad_documentos": len(documentos)},
        )
        db.commit()

    return BusquedaDocumentosLegalesOut(
        afiliado=AfiliadoLegalOut(
            id=afiliado.id, nombres=afiliado.nombres, apellidos=afiliado.apellidos,
            documento=afiliado.documento, nombre_coincide=nombre_coincide,
        ),
        documentos=documentos,
    )


@router.get("/{documento_id}/descarga")
def descargar_documento(
    documento_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    row = db.execute(
        select(DocumentoAsuncionDeuda)
        .join(Transaccion, Transaccion.id == DocumentoAsuncionDeuda.transaccion_id)
        .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
        .where(DocumentoAsuncionDeuda.id == documento_id, Afiliado.cooperativa_id == cooperativa_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pdf_bytes = storage_service.download_bytes(row.documento_storage_path)
    if pdf_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo del documento no está disponible.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="documento-asuncion-deuda-{documento_id}.pdf"'},
    )
