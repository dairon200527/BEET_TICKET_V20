"""
Reports (`/api/reportes`) — same rule as the dashboard: every query is
scoped to `admin.cooperativa_id`, never computed globally.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import resolve_cooperativa_scope
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.cupo_credito import CupoCredito
from app.models.enums import EstadoTransaccion, EstadoUnidadInventario
from app.models.transaccion import Transaccion
from app.models.unidad_inventario import UnidadInventario
from app.schemas.dashboard import RendimientoConvenioOut
from app.services.xlsx_export import XLSX_MEDIA_TYPE, build_xlsx, dated_filename

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def _calcular_rendimiento_convenios(cooperativa_id: int, db: Session) -> list[RendimientoConvenioOut]:
    convenios = db.execute(select(Convenio).where(Convenio.cooperativa_id == cooperativa_id)).scalars().all()

    resultado: list[RendimientoConvenioOut] = []
    for convenio in convenios:
        unidades_vendidas = db.execute(
            select(func.coalesce(func.sum(Transaccion.cantidad), 0)).where(
                Transaccion.convenio_id == convenio.id, Transaccion.estado == EstadoTransaccion.COMPLETADA
            )
        ).scalar_one()
        ingresos = db.execute(
            select(func.coalesce(func.sum(Transaccion.total), 0)).where(
                Transaccion.convenio_id == convenio.id, Transaccion.estado == EstadoTransaccion.COMPLETADA
            )
        ).scalar_one()
        conteos = dict(
            db.execute(
                select(UnidadInventario.estado, func.count())
                .where(UnidadInventario.convenio_id == convenio.id)
                .group_by(UnidadInventario.estado)
            ).all()
        )
        disponible = conteos.get(EstadoUnidadInventario.DISPONIBLE, 0)
        entregada = conteos.get(EstadoUnidadInventario.ENTREGADA, 0)
        redimida = conteos.get(EstadoUnidadInventario.REDIMIDA, 0)
        entregadas_o_redimidas = entregada + redimida
        tasa_redencion = int((redimida / entregadas_o_redimidas) * 100) if entregadas_o_redimidas else 0

        resultado.append(
            RendimientoConvenioOut(
                convenio_id=convenio.id,
                convenio_nombre=convenio.nombre,
                unidades_vendidas=unidades_vendidas,
                ingresos=ingresos,
                disponible=disponible,
                entregada=entregada,
                tasa_redencion=tasa_redencion,
            )
        )
    return resultado


@router.get("/rendimiento-convenios", response_model=list[RendimientoConvenioOut])
def rendimiento_convenios(
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> list[RendimientoConvenioOut]:
    return _calcular_rendimiento_convenios(cooperativa_id, db)


@router.get("/rendimiento-convenios/exportar")
def exportar_rendimiento_convenios(
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    """Same data as GET /rendimiento-convenios above, as a real .xlsx file
    — same columns shown on screen, so the export always matches what the
    admin is looking at."""
    filas = _calcular_rendimiento_convenios(cooperativa_id, db)
    headers = ["Convenio", "Vendidas", "Ingresos", "Disponible", "Entregada", "Tasa de redención (%)"]
    rows = [
        [f.convenio_nombre, f.unidades_vendidas, float(f.ingresos), f.disponible, f.entregada, f.tasa_redencion]
        for f in filas
    ]
    contenido = build_xlsx("Rendimiento por convenio", headers, rows)
    nombre_archivo = dated_filename("rendimiento_convenios")
    return Response(
        content=contenido,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/afiliados/exportar")
def exportar_afiliados(
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    """Affiliate roster with credit-quota info, as a real .xlsx file —
    covers the "listado de afiliados con cupo" report."""
    filas = db.execute(
        select(Afiliado, CupoCredito)
        .outerjoin(CupoCredito, CupoCredito.afiliado_id == Afiliado.id)
        .where(Afiliado.cooperativa_id == cooperativa_id)
        .order_by(Afiliado.nombres)
    ).all()

    headers = ["Documento", "Nombres", "Apellidos", "Correo", "Teléfono", "Estado", "Cupo total", "Cupo disponible"]
    rows = [
        [
            afiliado.documento,
            afiliado.nombres,
            afiliado.apellidos,
            afiliado.correo,
            afiliado.telefono or "",
            "Activo" if afiliado.estado else "Inactivo",
            float(cupo.cupo_total) if cupo else "",
            float(cupo.cupo_disponible) if cupo else "",
        ]
        for afiliado, cupo in filas
    ]
    contenido = build_xlsx("Afiliados", headers, rows)
    nombre_archivo = dated_filename("afiliados")
    return Response(
        content=contenido,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
