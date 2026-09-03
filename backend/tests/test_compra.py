"""Scenarios: the atomic purchase flow (POST /api/transacciones/comprar) —
card payment approved/rejected, cupo payment with signature, insufficient
inventory, insufficient cupo, and cross-tenant/inactive convenio guards
(see ../app/services/transaction_service.py)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.cupo_credito import CupoCredito
from app.models.documento_asuncion_deuda import DocumentoAsuncionDeuda
from app.models.transaccion_unidad import TransaccionUnidad
from app.models.unidad_inventario import UnidadInventario
from tests.conftest import afiliado_token, auth_headers, crear_unidades

# A minimal valid 1x1 transparent PNG, base64-encoded, no data-URL prefix.
FIRMA_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def test_compra_con_tarjeta_aprobada(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=3)
    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_a.id, "cantidad": 2, "metodo_pago": "TARJETA", "numero_tarjeta": "4111111111110000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "COMPLETADA"
    assert len(body["codigos"]) == 2
    assert body["resultado_pago"] is None
    assert body["motivo_rechazo"] is None

    disponibles = db_session.execute(
        select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_a.id, UnidadInventario.estado == "disponible")
    ).scalars().all()
    assert len(disponibles) == 1  # 3 - 2


def _comprar_tarjeta(client, token, convenio, numero_tarjeta):
    return client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio.id, "cantidad": 1, "metodo_pago": "TARJETA", "numero_tarjeta": numero_tarjeta},
        headers=auth_headers(token),
    )


def test_compra_con_tarjeta_rechazada_por_fondos_es_un_resultado_committeado(client, db_session, afiliado_a, convenio_a):
    """Card ending in 0001 — sandbox gateway simulates "insufficient
    funds" (see services/payment_gateway.py)."""
    crear_unidades(db_session, convenio_a, cantidad=3)
    token = afiliado_token(afiliado_a)
    r = _comprar_tarjeta(client, token, convenio_a, "4111111111110001")
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "RECHAZADA"
    assert body["resultado_pago"] == "rechazado_fondos"
    assert "fondos insuficientes" in body["motivo_rechazo"].lower()
    assert body["codigos"] == []

    # Nothing was touched — a rejected card payment happens strictly before
    # any inventory mutation, so the 3 units are still free (nothing was
    # ever locked/reserved for this failed attempt).
    disponibles = db_session.execute(
        select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_a.id, UnidadInventario.estado == "disponible")
    ).scalars().all()
    assert len(disponibles) == 3

    transaccion_id = body["id"]
    assert db_session.execute(
        select(TransaccionUnidad).where(TransaccionUnidad.transaccion_id == transaccion_id)
    ).scalars().all() == []
    assert db_session.execute(
        select(DocumentoAsuncionDeuda).where(DocumentoAsuncionDeuda.transaccion_id == transaccion_id)
    ).scalars().all() == []


def test_compra_con_tarjeta_rechazada_por_tarjeta_invalida(client, db_session, afiliado_a, convenio_a):
    """Card ending in 0002 — sandbox gateway simulates "invalid/expired
    card"."""
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    r = _comprar_tarjeta(client, token, convenio_a, "4111111111110002")
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "RECHAZADA"
    assert body["resultado_pago"] == "rechazado_invalida"
    assert "inválida" in body["motivo_rechazo"].lower()

    disponibles = db_session.execute(
        select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_a.id, UnidadInventario.estado == "disponible")
    ).scalars().all()
    assert len(disponibles) == 1


def test_compra_con_tarjeta_error_de_pasarela(client, db_session, afiliado_a, convenio_a):
    """Card ending in 0003 — sandbox gateway simulates a gateway
    timeout/error, distinct from an outright decline so the frontend can
    offer "reintentar" instead of just showing a rejection."""
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    r = _comprar_tarjeta(client, token, convenio_a, "4111111111110003")
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "RECHAZADA"
    assert body["resultado_pago"] == "error_pasarela"
    assert "pasarela" in body["motivo_rechazo"].lower()

    disponibles = db_session.execute(
        select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_a.id, UnidadInventario.estado == "disponible")
    ).scalars().all()
    assert len(disponibles) == 1


def test_compra_con_tarjeta_numero_no_reconocido_se_aprueba_por_defecto(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    r = _comprar_tarjeta(client, token, convenio_a, "4111111111119999")
    assert r.status_code == 201
    assert r.json()["estado"] == "COMPLETADA"


def test_compra_con_cupo_y_firma(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=2)
    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={
            "convenio_id": convenio_a.id,
            "cantidad": 1,
            "metodo_pago": "CUPO",
            "numero_cuotas": 3,
            "firma_base64": FIRMA_PNG_B64,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "COMPLETADA"

    cupo = db_session.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado_a.id)).scalar_one()
    assert cupo.cupo_disponible == cupo.cupo_total - convenio_a.precio_beet


def test_compra_con_cupo_genera_documento_real_con_firma_incrustada_via_storage_service(client, db_session, afiliado_a, convenio_a, admin_a):
    """Section 21's "Documento de deuda" checklist, end to end: a real
    PDF is generated (not empty, not corrupt — starts with the real %PDF
    magic bytes), the captured signature is actually drawn into it (a
    real embedded image, not just referenced), the bytes are reachable
    only through storage_service (never a raw filesystem/bucket path),
    and it's downloadable by the admin afterward."""
    import io

    from pypdf import PdfReader

    from app.services import storage_service
    from tests.conftest import admin_token

    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_a.id, "cantidad": 1, "metodo_pago": "CUPO", "numero_cuotas": 3, "firma_base64": FIRMA_PNG_B64},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    transaccion_id = r.json()["id"]

    documento = db_session.execute(
        select(DocumentoAsuncionDeuda).where(DocumentoAsuncionDeuda.transaccion_id == transaccion_id)
    ).scalar_one()
    assert documento.documento_storage_path  # never blank
    assert not documento.documento_storage_path.startswith(("/", "C:", "\\"))  # a storage KEY, never a raw filesystem path
    assert documento.firma_storage_path

    pdf_bytes = storage_service.download_bytes(documento.documento_storage_path)
    assert pdf_bytes is not None
    assert pdf_bytes.startswith(b"%PDF")  # real, non-corrupt PDF
    assert len(pdf_bytes) > 500  # not an empty/near-empty file

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    assert len(reader.pages[0].images) >= 1  # the captured signature, actually embedded

    firma_bytes = storage_service.download_bytes(documento.firma_storage_path)
    assert firma_bytes is not None
    assert firma_bytes.startswith(b"\x89PNG")

    # The admin's own download endpoint must serve the exact same bytes —
    # never a different, unauthenticated, or raw-path route.
    descarga = client.get(f"/api/documentos/{documento.id}/descarga", headers=auth_headers(admin_token(admin_a)))
    assert descarga.status_code == 200
    assert descarga.content == pdf_bytes


def test_compra_con_cupo_insuficiente_falla_y_no_toca_inventario(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=2)
    cupo = db_session.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado_a.id)).scalar_one()
    cupo.cupo_disponible = 100  # far less than one unit's precio_beet (8000)
    db_session.commit()

    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={
            "convenio_id": convenio_a.id,
            "cantidad": 1,
            "metodo_pago": "CUPO",
            "numero_cuotas": 1,
            "firma_base64": FIRMA_PNG_B64,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 400

    disponibles = db_session.execute(
        select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_a.id, UnidadInventario.estado == "disponible")
    ).scalars().all()
    assert len(disponibles) == 2


def test_compra_con_inventario_insuficiente_falla(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_a.id, "cantidad": 2, "metodo_pago": "TARJETA", "numero_tarjeta": "4111111111110000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 400


def test_compra_de_convenio_de_otra_cooperativa_es_404(client, db_session, afiliado_a, cooperativa_b):
    from app.models.convenio import Convenio

    convenio_otra = Convenio(
        cooperativa_id=cooperativa_b.id, nombre="De otra coop", precio_publico=1000, precio_beet=800, fecha_inicio="2024-01-01"
    )
    db_session.add(convenio_otra)
    db_session.commit()
    crear_unidades(db_session, convenio_otra, cantidad=1)

    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_otra.id, "cantidad": 1, "metodo_pago": "TARJETA", "numero_tarjeta": "4111111111110000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 404


def test_compra_de_convenio_inactivo_falla(client, db_session, afiliado_a, convenio_a):
    convenio_a.estado = False
    db_session.commit()
    crear_unidades(db_session, convenio_a, cantidad=1)

    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_a.id, "cantidad": 1, "metodo_pago": "TARJETA", "numero_tarjeta": "4111111111110000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 400


def test_cupo_sin_firma_es_rechazado_por_validacion(client, afiliado_a, convenio_a):
    token = afiliado_token(afiliado_a)
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_a.id, "cantidad": 1, "metodo_pago": "CUPO", "numero_cuotas": 3},
        headers=auth_headers(token),
    )
    assert r.status_code == 422
