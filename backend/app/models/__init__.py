"""Import every model so `Base.metadata` sees all 11 tables — required
for Alembic autogenerate and for the test suite's create_all()."""
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.cooperativa import Cooperativa
from app.models.cupo_credito import CupoCredito
from app.models.documento_asuncion_deuda import DocumentoAsuncionDeuda
from app.models.log_auditoria import LogAuditoria
from app.models.plantilla import Plantilla
from app.models.transaccion import Transaccion
from app.models.transaccion_unidad import TransaccionUnidad
from app.models.unidad_inventario import UnidadInventario
from app.models.usuario_admin import UsuarioAdmin

__all__ = [
    "Cooperativa",
    "Afiliado",
    "UsuarioAdmin",
    "Convenio",
    "Plantilla",
    "UnidadInventario",
    "CupoCredito",
    "Transaccion",
    "TransaccionUnidad",
    "DocumentoAsuncionDeuda",
    "LogAuditoria",
]
