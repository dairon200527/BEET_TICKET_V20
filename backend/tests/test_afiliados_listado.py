"""GET /api/afiliados now returns cupo_total/cupo_disponible directly on
each row (a single outerjoin, not a per-row lookup) so the admin listing
can show the cupo at a glance without opening "Ver detalle" for every
affiliate — see routers/afiliados.py."""
from __future__ import annotations

from app.models.afiliado import Afiliado
from tests.conftest import admin_token, auth_headers


def test_listar_afiliados_incluye_cupo_sin_consultas_por_fila(client, db_session, admin_a, afiliado_a, cooperativa_a):
    afiliado_sin_cupo = Afiliado(
        cooperativa_id=cooperativa_a.id, documento="1000000099", nombres="Sin", apellidos="Cupo", correo="sincupo@test.com"
    )
    db_session.add(afiliado_sin_cupo)
    db_session.commit()

    token = admin_token(admin_a)
    r = client.get("/api/afiliados", headers=auth_headers(token))
    assert r.status_code == 200
    items = {a["documento"]: a for a in r.json()["items"]}

    con_cupo = items[afiliado_a.documento]
    assert float(con_cupo["cupo_total"]) == 500000
    assert float(con_cupo["cupo_disponible"]) == 500000

    sin_cupo = items["1000000099"]
    assert sin_cupo["cupo_total"] is None
    assert sin_cupo["cupo_disponible"] is None
