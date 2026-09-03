"""
Dashboard (`/api/dashboard`) — every figure here is computed by querying
PostgreSQL scoped to `cooperativa_id`; nothing is ever aggregated
globally or filtered in the frontend.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import resolve_cooperativa_scope
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.enums import EstadoTransaccion, MetodoPago
from app.models.transaccion import Transaccion
from app.schemas.dashboard import DashboardStatsOut, VentasPorFormaDePago

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
def stats(cooperativa_id: int = Depends(resolve_cooperativa_scope), db: Session = Depends(get_db)) -> DashboardStatsOut:
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    base_mes = (
        select(Transaccion)
        .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
        .where(
            Afiliado.cooperativa_id == cooperativa_id,
            Transaccion.estado == EstadoTransaccion.COMPLETADA,
            Transaccion.created_at >= inicio_mes,
        )
    )

    ventas_del_mes = db.execute(
        select(func.coalesce(func.sum(Transaccion.total), 0)).select_from(base_mes.subquery())
    ).scalar_one()

    ahorro_generado = db.execute(
        select(func.coalesce(func.sum((Convenio.precio_publico - Convenio.precio_beet) * Transaccion.cantidad), 0))
        .select_from(Transaccion)
        .join(Convenio, Convenio.id == Transaccion.convenio_id)
        .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
        .where(Afiliado.cooperativa_id == cooperativa_id, Transaccion.estado == EstadoTransaccion.COMPLETADA)
    ).scalar_one()

    # `unidades_inventario` has no expiration date column in the real
    # schema — the closest real signal is convenios whose vigencia is
    # ending soon.
    convenios_por_vencer = db.execute(
        select(func.count()).select_from(Convenio).where(
            Convenio.cooperativa_id == cooperativa_id,
            Convenio.estado.is_(True),
            Convenio.fecha_fin.is_not(None),
            Convenio.fecha_fin >= hoy,
            Convenio.fecha_fin <= hoy + timedelta(days=30),
        )
    ).scalar_one()

    convenios_activos = db.execute(
        select(func.count()).select_from(Convenio).where(
            Convenio.cooperativa_id == cooperativa_id, Convenio.estado.is_(True)
        )
    ).scalar_one()

    por_metodo = dict(
        db.execute(
            select(Transaccion.metodo_pago, func.coalesce(func.sum(Transaccion.total), 0))
            .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
            .where(Afiliado.cooperativa_id == cooperativa_id, Transaccion.estado == EstadoTransaccion.COMPLETADA)
            .group_by(Transaccion.metodo_pago)
        ).all()
    )
    tarjeta = por_metodo.get(MetodoPago.TARJETA, Decimal(0))
    cupo = por_metodo.get(MetodoPago.CUPO, Decimal(0))
    total = tarjeta + cupo
    pct_tarjeta = int((tarjeta / total * 100)) if total else 0
    pct_cupo = 100 - pct_tarjeta if total else 0

    return DashboardStatsOut(
        ventas_del_mes=ventas_del_mes,
        ahorro_generado=ahorro_generado,
        convenios_por_vencer=convenios_por_vencer,
        convenios_activos=convenios_activos,
        ventas_por_forma_de_pago=VentasPorFormaDePago(tarjeta=tarjeta, cupo=cupo, pct_tarjeta=pct_tarjeta, pct_cupo=pct_cupo),
    )
