"""
Tickets (`/api/tickets`) — one issued `unidad_inventario` belonging to one
of the authenticated affiliate's own transactions. A ticket PDF is
rendered fresh from authoritative DB data on every download (never cached
across requests) and is NEVER downloadable by another affiliate —
ownership is re-verified on every request via the transaccion_unidades
join, never trusted from a client-supplied transaccion_id or afiliado_id.

`/me/{unidad_id}/descarga` returns the actual PDF bytes directly
(`Content-Type: application/pdf`), not a JSON envelope with a URL — this
is what lets the frontend hand the response straight to the browser
(`Blob` + `URL.createObjectURL`) for an immediate, real download/preview.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_affiliate
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.transaccion import Transaccion
from app.models.transaccion_unidad import TransaccionUnidad
from app.models.unidad_inventario import UnidadInventario
from app.schemas.ticket import TicketOut
from app.services import pdf_service

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _mis_tickets_query(afiliado_id: int):
    return (
        select(UnidadInventario, TransaccionUnidad.transaccion_id)
        .join(TransaccionUnidad, TransaccionUnidad.unidad_id == UnidadInventario.id)
        .join(Transaccion, Transaccion.id == TransaccionUnidad.transaccion_id)
        .where(Transaccion.afiliado_id == afiliado_id)
    )


@router.get("/me", response_model=list[TicketOut])
def mis_tickets(afiliado: Afiliado = Depends(get_current_affiliate), db: Session = Depends(get_db)) -> list[TicketOut]:
    rows = db.execute(_mis_tickets_query(afiliado.id).order_by(UnidadInventario.id.desc())).all()
    return [
        TicketOut(
            id=unidad.id,
            codigo=unidad.codigo,
            convenio_id=unidad.convenio_id,
            transaccion_id=transaccion_id,
            estado=unidad.estado,
        )
        for unidad, transaccion_id in rows
    ]


@router.get("/me/{unidad_id}/descarga")
def descargar_mi_ticket(unidad_id: int, afiliado: Afiliado = Depends(get_current_affiliate), db: Session = Depends(get_db)) -> Response:
    row = db.execute(_mis_tickets_query(afiliado.id).where(UnidadInventario.id == unidad_id)).one_or_none()
    if row is None:
        # Hides both "doesn't exist" and "belongs to someone else" alike.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado.")
    unidad, transaccion_id = row

    transaccion = db.get(Transaccion, transaccion_id)
    convenio = db.get(Convenio, unidad.convenio_id)

    # Every unit belonging to this SAME transacción (not just this one) —
    # real rows from unidades_inventario, joined the exact same way
    # _mis_tickets_query does. This is what lets a "layout" plantilla
    # (see template_engine.py) draw one QR/row per unit for a
    # cantidad > 1 purchase, instead of only the single unit this PDF is
    # for; never fabricated, never any other convenio/transacción's units.
    hermanas = db.execute(
        select(UnidadInventario)
        .join(TransaccionUnidad, TransaccionUnidad.unidad_id == UnidadInventario.id)
        .where(TransaccionUnidad.transaccion_id == transaccion.id)
    ).scalars().all()

    pdf_bytes = pdf_service.generar_ticket(
        convenio,
        unidad,
        variables={
            "afiliado_nombre": f"{afiliado.nombres} {afiliado.apellidos}",
            "afiliado_documento": afiliado.documento,
            "transaccion_id": transaccion.id,
            "fecha_compra": transaccion.created_at.isoformat() if transaccion.created_at else "",
            "cantidad": transaccion.cantidad,
            "unidades_hermanas": [{"codigo": h.codigo, "estado": h.estado.value} for h in hermanas],
        },
    )
    object_key = pdf_service.upload_ticket_pdf(
        cooperativa_id=afiliado.cooperativa_id, transaccion_id=transaccion.id, unidad_id=unidad.id, pdf_bytes=pdf_bytes
    )

    tu = db.execute(select(TransaccionUnidad).where(TransaccionUnidad.unidad_id == unidad.id)).scalar_one_or_none()
    if tu is not None:
        tu.ticket_storage_path = object_key
        db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ticket-{unidad.codigo}.pdf"'},
    )
