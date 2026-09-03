"""
The atomic purchase flow.

Every step below runs inside the SAME database transaction as the caller
(a router opens no transaction of its own — SQLAlchemy's `Session` starts
one implicitly on first use, and this function ends it with a single
`commit()` or `rollback()`), with ONE deliberate exception: a card
payment REJECTED by the mock gateway is its own committed outcome
(`EstadoTransaccion.RECHAZADA`) — a rejected transaction is a real
business event the admin panel's transaction list is meant to show, not
something to pretend never happened. Inventory and cupo are never
touched before a card payment is confirmed approved, so nothing needs
"undoing" in the rejection case.

Row-level locking: candidate `unidades_inventario` rows are selected with
`SELECT ... FOR UPDATE` before being assigned, so two concurrent
purchases against the same convenio can never both be handed the same
unit. The DB-level UNIQUE constraint on `transaccion_unidades.unidad_id`
(see models/transaccion_unidad.py) backs this up as a last line of
defense even if application-level locking were ever bypassed by a bug.

NOTE on scope: unlike an earlier design assumption, the real
`cooperativas` table has no `tarjeta_habilitada`/`cupo_habilitado`
columns — there is no per-cooperativa payment-method toggle to check
anymore (see SCHEMA_NOTES.md). Both payment methods are always available;
if a cooperativa needs to disable one, that's a schema/product decision
to make explicitly later, not something this pass silently reintroduces
as apphard-coded config.
"""
from __future__ import annotations

import base64
import binascii
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.documento_asuncion_deuda import DocumentoAsuncionDeuda
from app.models.enums import EstadoDocumento, EstadoTransaccion, EstadoTransaccionUnidad, EstadoUnidadInventario, MetodoPago
from app.models.transaccion import Transaccion
from app.models.transaccion_unidad import TransaccionUnidad
from app.models.unidad_inventario import UnidadInventario
from app.schemas.transaccion import CompraRequest
from app.services import audit_service, cupo_service, payment_gateway, pdf_service
from app.utils.file_validation import validate_size

MAX_FIRMA_BYTES = 2 * 1024 * 1024  # 2 MB is generous for a canvas signature PNG


def _load_convenio_or_404(db: Session, afiliado: Afiliado, convenio_id: int) -> Convenio:
    convenio = db.get(Convenio, convenio_id)
    if convenio is None or convenio.cooperativa_id != afiliado.cooperativa_id:
        # 404, not 400/403 — a cross-tenant convenio must never be
        # confirmed to exist at all.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convenio no encontrado.")
    if not convenio.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El convenio no está activo.")
    hoy = date.today()
    if convenio.fecha_inicio > hoy or (convenio.fecha_fin is not None and convenio.fecha_fin < hoy):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El convenio no está vigente.")
    return convenio


def _decode_firma(firma_base64: str) -> bytes:
    try:
        data = base64.b64decode(firma_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La firma no es un PNG en base64 válido.")
    validate_size(len(data), max_bytes=MAX_FIRMA_BYTES)
    if not data.startswith(b"\x89PNG"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La firma debe ser una imagen PNG.")
    return data


def procesar_compra(
    db: Session, afiliado: Afiliado, payload: CompraRequest
) -> tuple[Transaccion, payment_gateway.ResultadoPago | None]:
    """Executes the full atomic purchase flow and returns the resulting,
    committed `Transaccion` (which may be `RECHAZADA` for a card payment
    the mock gateway rejected — that is a successful, valid outcome of
    this function, not an exception) alongside the raw gateway result for
    a TARJETA payment (`None` for CUPO, which never calls the gateway) —
    the router uses it to tell the affiliate exactly which of the 4
    simulated outcomes happened, without persisting that reason anywhere.
    Raises `HTTPException` on any other failure (insufficient inventory,
    insufficient cupo, invalid convenio), guaranteeing `db.rollback()` has
    already run in that case."""
    convenio = _load_convenio_or_404(db, afiliado, payload.convenio_id)

    firma_bytes: bytes | None = None
    if payload.metodo_pago == MetodoPago.CUPO:
        # Decoded up front (before any writes) so a malformed signature
        # never leaves the DB transaction half-open.
        firma_bytes = _decode_firma(payload.firma_base64)  # type: ignore[arg-type]

    try:
        subtotal: Decimal = convenio.precio_beet * payload.cantidad
        total: Decimal = subtotal

        transaccion = Transaccion(
            afiliado_id=afiliado.id,
            convenio_id=convenio.id,
            cantidad=payload.cantidad,
            subtotal=subtotal,
            total=total,
            metodo_pago=payload.metodo_pago,
            numero_cuotas=payload.numero_cuotas,
            estado=EstadoTransaccion.PENDIENTE,
        )
        db.add(transaccion)
        db.flush()

        resultado_pago: payment_gateway.ResultadoPago | None = None
        if payload.metodo_pago == MetodoPago.TARJETA:
            # Never touch inventory/cupo before the (mock) gateway has
            # actually approved the charge.
            resultado_pago = payment_gateway.procesar_pago_tarjeta(monto=total, numero_tarjeta=payload.numero_tarjeta)  # type: ignore[arg-type]
            if not resultado_pago.aprobado:
                transaccion.estado = EstadoTransaccion.RECHAZADA
                audit_service.record(
                    db, usuario_admin_id=None,
                    accion="compra_rechazada", tabla_afectada="transacciones", registro_id=transaccion.id,
                    detalles={
                        "afiliado_id": afiliado.id, "convenio_id": convenio.id,
                        "tipo": resultado_pago.tipo, "motivo": resultado_pago.motivo_rechazo,
                    },
                )
                db.commit()
                db.refresh(transaccion)
                return transaccion, resultado_pago
            transaccion.referencia_pago = resultado_pago.referencia

        # Find AND lock the candidate units in one shot. Without
        # `skip_locked`, a concurrent purchase touching the same rows
        # blocks us until it commits or rolls back — so we never read a
        # unit as "available" that another in-flight purchase already
        # claimed a moment ago.
        unidades = (
            db.execute(
                select(UnidadInventario)
                .where(
                    UnidadInventario.convenio_id == convenio.id,
                    UnidadInventario.estado == EstadoUnidadInventario.DISPONIBLE,
                )
                .order_by(UnidadInventario.id)
                .limit(payload.cantidad)
                .with_for_update()
            )
            .scalars()
            .all()
        )

        if len(unidades) < payload.cantidad:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inventario insuficiente para completar la compra.")

        if payload.metodo_pago == MetodoPago.CUPO:
            # Debit the credit quota atomically — this raises (and the
            # outer except rolls everything back, including the still-
            # DISPONIBLE units above, since nothing has been mutated yet)
            # if the balance is insufficient.
            cupo_service.verify_and_debit(db, afiliado, total)

        ahora = datetime.now(timezone.utc)
        for unidad in unidades:
            unidad.estado = EstadoUnidadInventario.ENTREGADA
            db.add(
                TransaccionUnidad(
                    transaccion_id=transaccion.id,
                    unidad_id=unidad.id,
                    estado=EstadoTransaccionUnidad.ENTREGADA,
                    fecha_entrega=ahora,
                )
            )

        if payload.metodo_pago == MetodoPago.CUPO:
            firma_path = pdf_service.upload_signature_png(
                cooperativa_id=afiliado.cooperativa_id, transaccion_id=transaccion.id, png_bytes=firma_bytes  # type: ignore[arg-type]
            )
            # The signature was captured synchronously as part of this
            # same request — the document is FIRMADO immediately, not
            # left PENDIENTE awaiting a later step that doesn't exist.
            documento = DocumentoAsuncionDeuda(
                transaccion_id=transaccion.id,
                firma_storage_path=firma_path,
                documento_storage_path="pending",  # overwritten below once the PDF exists
                estado=EstadoDocumento.FIRMADO,
                fecha_firma=ahora,
            )
            db.add(documento)
            db.flush()

            pdf_bytes = pdf_service.generar_documento_asuncion_deuda(
                variables={
                    "afiliado_nombre": f"{afiliado.nombres} {afiliado.apellidos}",
                    "afiliado_documento": afiliado.documento,
                    "transaccion_id": transaccion.id,
                    "total": str(total),
                    "numero_cuotas": payload.numero_cuotas,
                    "fecha": ahora.isoformat(),
                },
                firma_png=firma_bytes,
            )
            documento.documento_storage_path = pdf_service.upload_debt_document_pdf(
                cooperativa_id=afiliado.cooperativa_id, transaccion_id=transaccion.id, pdf_bytes=pdf_bytes
            )

        transaccion.estado = EstadoTransaccion.COMPLETADA

        # `logs_auditoria` has no `afiliado_id`/`cooperativa_id` column at
        # all (see SCHEMA_NOTES.md) — it was designed around admin-
        # initiated actions (`usuario_admin_id`). For an affiliate-
        # initiated purchase there is no admin to attribute it to, so
        # `usuario_admin_id` is left NULL and the affiliate/convenio
        # identifiers are recorded inside `detalles` instead — the closest
        # honest fit the real schema allows, rather than adding a new
        # column without sign-off.
        audit_service.record(
            db, usuario_admin_id=None,
            accion="compra_completada", tabla_afectada="transacciones", registro_id=transaccion.id,
            detalles={
                "afiliado_id": afiliado.id,
                "convenio_id": convenio.id,
                "cantidad": payload.cantidad,
                "metodo_pago": payload.metodo_pago.value,
                "total": str(total),
            },
        )

        db.commit()
        db.refresh(transaccion)
        return transaccion, resultado_pago

    except Exception:
        # Covers HTTPException (insufficient inventory / insufficient
        # cupo / inactive affiliate, etc.) and any unexpected error alike
        # — either way, nothing partial is left committed.
        db.rollback()
        raise
