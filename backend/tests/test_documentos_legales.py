"""
Documentos-legales search (dispute support: "el afiliado dice que nunca
aceptó ese compromiso") — GET /api/documentos/legales/buscar and
GET /api/documentos/{id}/descarga. See app/routers/documentos.py.
"""
from __future__ import annotations

from app.models.documento_asuncion_deuda import DocumentoAsuncionDeuda
from app.models.enums import EstadoDocumento, EstadoTransaccion, MetodoPago
from app.models.log_auditoria import LogAuditoria
from app.models.transaccion import Transaccion
from app.services import storage_service
from tests.conftest import admin_token, auth_headers


def _crear_documento_legal(db_session, afiliado, convenio, *, pdf_bytes=b"%PDF-1.4 contenido de prueba") -> DocumentoAsuncionDeuda:
    transaccion = Transaccion(
        afiliado_id=afiliado.id, convenio_id=convenio.id, cantidad=1,
        subtotal=100000, total=100000, metodo_pago=MetodoPago.CUPO, numero_cuotas=3,
        estado=EstadoTransaccion.COMPLETADA,
    )
    db_session.add(transaccion)
    db_session.flush()

    storage_path = storage_service.generate_object_key("documentos-asuncion-deuda", afiliado.cooperativa_id, "transaccion", transaccion.id, ".pdf")
    storage_service.upload_bytes(storage_path, pdf_bytes, "application/pdf")

    doc = DocumentoAsuncionDeuda(transaccion_id=transaccion.id, documento_storage_path=storage_path, estado=EstadoDocumento.FIRMADO)
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_buscar_por_documento_encuentra_afiliado_y_sus_documentos(client, admin_a, afiliado_a, convenio_a, db_session):
    _crear_documento_legal(db_session, afiliado_a, convenio_a)
    token = admin_token(admin_a)

    resp = client.get(f"/api/documentos/legales/buscar?documento={afiliado_a.documento}", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["afiliado"]["documento"] == afiliado_a.documento
    assert len(data["documentos"]) == 1
    assert data["documentos"][0]["convenio_nombre"] == convenio_a.nombre
    assert data["documentos"][0]["numero_cuotas"] == 3


def test_nombre_es_solo_confirmacion_nunca_filtro(client, admin_a, afiliado_a, convenio_a, db_session):
    """A wrong/mismatched `nombres` must NOT hide a real match on
    `documento` — it only flips `nombre_coincide` to False."""
    _crear_documento_legal(db_session, afiliado_a, convenio_a)
    token = admin_token(admin_a)

    resp = client.get(
        f"/api/documentos/legales/buscar?documento={afiliado_a.documento}&nombres=NombreCompletamenteDistinto",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["documentos"]) == 1
    assert data["afiliado"]["nombre_coincide"] is False


def test_documento_inexistente_devuelve_vacio_no_404(client, admin_a):
    token = admin_token(admin_a)
    resp = client.get("/api/documentos/legales/buscar?documento=999999999", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {"afiliado": None, "documentos": []}


def test_super_admin_sin_cooperativa_seleccionada_es_400(client, superadmin_sin_cooperativa):
    token = admin_token(superadmin_sin_cooperativa)
    resp = client.get("/api/documentos/legales/buscar?documento=1000000001", headers=auth_headers(token))
    assert resp.status_code == 400


def test_admin_de_otra_cooperativa_nunca_ve_documentos_de_afiliado_ajeno(client, admin_b, afiliado_a, convenio_a, db_session):
    _crear_documento_legal(db_session, afiliado_a, convenio_a)
    token = admin_token(admin_b)  # admin_b belongs to cooperativa_b, afiliado_a to cooperativa_a

    resp = client.get(f"/api/documentos/legales/buscar?documento={afiliado_a.documento}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {"afiliado": None, "documentos": []}


def test_busqueda_con_resultados_queda_en_logs_auditoria(client, admin_a, afiliado_a, convenio_a, db_session):
    _crear_documento_legal(db_session, afiliado_a, convenio_a)
    token = admin_token(admin_a)

    client.get(f"/api/documentos/legales/buscar?documento={afiliado_a.documento}", headers=auth_headers(token))

    log = db_session.query(LogAuditoria).filter_by(accion="documentos_legales_consultados").one_or_none()
    assert log is not None
    assert log.usuario_admin_id == admin_a.id
    assert log.registro_id == afiliado_a.id
    assert log.detalles["documento"] == afiliado_a.documento


def test_busqueda_sin_documentos_no_genera_log(client, admin_a, afiliado_a, db_session):
    """afiliado_a exists (from the fixture) but has never signed anything
    — nothing sensitive was actually disclosed, so nothing to log."""
    token = admin_token(admin_a)
    client.get(f"/api/documentos/legales/buscar?documento={afiliado_a.documento}", headers=auth_headers(token))

    log = db_session.query(LogAuditoria).filter_by(accion="documentos_legales_consultados").one_or_none()
    assert log is None


def test_descarga_devuelve_el_pdf_real(client, admin_a, afiliado_a, convenio_a, db_session):
    doc = _crear_documento_legal(db_session, afiliado_a, convenio_a, pdf_bytes=b"%PDF-1.4 bytes reales de prueba")
    token = admin_token(admin_a)

    resp = client.get(f"/api/documentos/{doc.id}/descarga", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == b"%PDF-1.4 bytes reales de prueba"


def test_descarga_de_documento_de_otra_cooperativa_da_404(client, admin_b, afiliado_a, convenio_a, db_session):
    doc = _crear_documento_legal(db_session, afiliado_a, convenio_a)
    token = admin_token(admin_b)

    resp = client.get(f"/api/documentos/{doc.id}/descarga", headers=auth_headers(token))
    assert resp.status_code == 404
