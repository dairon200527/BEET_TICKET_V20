import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import Button, { IconButton } from '../../../components/ui/Button';
import { Input, Select } from '../../../components/ui/Field';
import { IconBuscar, IconDescargar, IconPlus, IconUpload } from '../../../components/ui/Icons';
import { Dropdown, Pagination } from '../../../components/ui/Nav';
import { StatusBadge, Badge } from '../../../components/ui/Badge';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import PermissionGate from '../../../components/ui/PermissionGate';
import Modal, { ConfirmDialog } from '../../../components/ui/Modal';
import FileUploader from '../../../components/ui/FileUploader';
import Alert from '../../../components/ui/Alert';
import { useTableState } from '../../../hooks/useTableState';
import * as convenioService from '../../../services/convenioService';
import * as inventarioService from '../../../services/inventarioService';
import { ApiError } from '../../../services/apiClient';
import { formatCOP, formatDate } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';
import { useAuth } from '../../../context/AuthContext';
import { useCooperativa } from '../../../context/CooperativaContext';
import RequireCooperativaSeleccionada from '../../../components/layout/RequireCooperativaSeleccionada';

// NOTE: unlike an earlier design assumption, the real `convenios` table
// has no `marca`, `categoria`, `tope`, or `tope_periodicidad` columns —
// those filters/columns have been removed to match (see SCHEMA_NOTES.md).
// `estado` is a plain boolean, and vigencia is `fecha_inicio`/`fecha_fin`.
export default function ConveniosList() {
  useSetBreadcrumbs([{ label: 'Convenios' }]);
  const navigate = useNavigate();
  const { push } = useToast();
  const { permissions } = useAuth();
  const { necesitaSeleccion, selectedId, selected, isSuperAdmin } = useCooperativa();

  const [convenios, setConvenios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [inventarioPorConvenio, setInventarioPorConvenio] = useState({});
  const [openMenuId, setOpenMenuId] = useState(null);
  const [confirmTarget, setConfirmTarget] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [exporting, setExporting] = useState(false);

  const cargar = useCallback(() => {
    if (necesitaSeleccion) return;
    setLoading(true);
    setError(null);
    convenioService
      .listarConvenios({ pageSize: 100 })
      .then((data) => {
        setConvenios(data.items);
        // One summary call per convenio — fine at this dataset size for an
        // integration test; a later pass could add an aggregate endpoint.
        Promise.all(
          data.items.map((c) =>
            inventarioService
              .resumenInventario(c.id)
              .then((r) => [c.id, r])
              .catch(() => [c.id, null])
          )
        ).then((pairs) => setInventarioPorConvenio(Object.fromEntries(pairs)));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No pudimos cargar los convenios.'))
      .finally(() => setLoading(false));
  }, [necesitaSeleccion]);

  useEffect(() => { cargar(); }, [cargar, selectedId]);

  const { search, setSearch, filters, setFilter, pageRows, page, setPage, totalPages, total } = useTableState({
    data: convenios,
    searchFields: ['nombre', 'id'],
    pageSize: 8,
    // Only active convenios by default — a deactivated one shouldn't
    // look identical to an active one in the main list; "Todo estado"
    // in the Select above still lets an admin bring inactive ones back.
    defaultFilters: { estado: true },
  });

  const handleExport = async () => {
    setExporting(true);
    try {
      const { blob, filename } = await convenioService.exportarConvenios();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      push({ title: 'Convenios exportados', description: filename });
    } catch (err) {
      push({ title: 'No se pudo exportar', description: err.message, variant: 'error' });
    } finally {
      setExporting(false);
    }
  };

  const handleUpload = async (file) => {
    setUploading(true);
    setUploadResult(null);
    try {
      const result = await convenioService.cargaMasivaConvenios(file);
      setUploadResult(result);
      push({
        title: result.invalidos > 0 ? 'Carga procesada con filas inválidas' : 'Convenios procesados',
        description: result.detail,
        variant: result.invalidos > 0 ? 'error' : 'success',
      });
      cargar();
    } catch (err) {
      push({ title: 'No se pudo procesar el archivo', description: err.message, variant: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const toggleEstado = async (convenio) => {
    const nuevoEstado = !convenio.estado;
    try {
      const actualizado = await convenioService.actualizarConvenio(convenio.id, { estado: nuevoEstado });
      setConvenios((prev) => prev.map((c) => (c.id === convenio.id ? actualizado : c)));
      push({ title: nuevoEstado ? 'Convenio activado' : 'Convenio desactivado', description: convenio.nombre });
    } catch (err) {
      push({ title: 'No se pudo actualizar el convenio', description: err.message, variant: 'error' });
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Convenios</h1>
          <p className="page-subtitle">Precios, ahorro, vigencia, inventario y estado de cada convenio, desde PostgreSQL.</p>
          {isSuperAdmin && (
            <p className="text-caption" style={{ marginTop: 4 }}>
              {selected ? `Estás gestionando datos de: ${selected.nombre}` : 'Selecciona una cooperativa arriba para empezar.'}
            </p>
          )}
        </div>
        <div className="page-header-actions">
          <Button variant="secondary" icon={<IconDescargar size={15} color="#1F2937" />} loading={exporting} onClick={handleExport} disabled={necesitaSeleccion}>Exportar</Button>
          <PermissionGate>
            <Button variant="secondary" icon={<IconUpload size={16} color="#1F2937" />} onClick={() => setUploadOpen(true)} disabled={necesitaSeleccion}>Cargar convenios</Button>
            <Button icon={<IconPlus color="#fff" />} onClick={() => navigate('/convenios/nuevo')} disabled={necesitaSeleccion}>Crear convenio</Button>
          </PermissionGate>
        </div>
      </div>

      {necesitaSeleccion ? (
        <RequireCooperativaSeleccionada />
      ) : (
      <div className="table-card">
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <label className="input-affix-wrap" style={{ width: 260 }}>
              <span className="input-affix-icon"><IconBuscar size={16} color="var(--text-muted)" /></span>
              <Input placeholder="Buscar por nombre o ID" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <Select
              style={{ width: 140 }}
              value={filters.estado === undefined ? '' : String(filters.estado)}
              onChange={(e) => setFilter('estado', e.target.value === '' ? undefined : e.target.value === 'true')}
            >
              <option value="">Todo estado</option>
              <option value="true">Activo</option>
              <option value="false">Inactivo</option>
            </Select>
          </div>
        </div>

        {loading ? (
          <LoadingState title="Cargando convenios desde PostgreSQL…" />
        ) : error ? (
          <ErrorState description={error} onRetry={cargar} />
        ) : pageRows.length === 0 ? (
          total === 0 ? (
            <EmptyState title="No hay convenios registrados" description="Crea el primer convenio para esta cooperativa." />
          ) : (
            <EmptyState title="Sin convenios que coincidan" description="Ajusta los filtros o el término de búsqueda." />
          )
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Convenio</th>
                  <th className="right">Precio BEET</th>
                  <th className="right">Ahorro</th>
                  <th>Vigencia</th>
                  <th>Inventario</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((c) => {
                  const ahorroPct = Math.round(((c.precio_publico - c.precio_beet) / c.precio_publico) * 100);
                  const inv = inventarioPorConvenio[c.id];
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/convenios/${c.id}`} className="cell-primary" style={{ color: 'var(--text-primary)', textDecoration: 'none' }}>{c.nombre}</Link>
                        <div className="cell-muted">{c.descripcion ?? '—'}</div>
                      </td>
                      <td className="right tabular">{formatCOP(c.precio_beet)}</td>
                      <td className="right">
                        <Badge tone="green" dot>Ahorras {ahorroPct}%</Badge>
                      </td>
                      <td className="text-small">{formatDate(c.fecha_inicio)}{c.fecha_fin ? ` – ${formatDate(c.fecha_fin)}` : ' – sin fin'}</td>
                      <td className="text-small">{inv ? `${inv.disponible} disponibles` : '—'}</td>
                      <td><StatusBadge status={c.estado} /></td>
                      <td className="right" style={{ position: 'relative' }}>
                        <IconButton
                          size="sm"
                          label="Más acciones"
                          onClick={() => setOpenMenuId(openMenuId === c.id ? null : c.id)}
                          icon={<svg width="16" height="16" viewBox="0 0 20 20" fill="none"><circle cx="4" cy="10" r="1.4" fill="#1F2937" /><circle cx="10" cy="10" r="1.4" fill="#1F2937" /><circle cx="16" cy="10" r="1.4" fill="#1F2937" /></svg>}
                        />
                        <Dropdown
                          open={openMenuId === c.id}
                          onClose={() => setOpenMenuId(null)}
                          style={{ top: 40, right: 0 }}
                          items={[
                            { label: 'Ver detalle', onClick: () => navigate(`/convenios/${c.id}`) },
                            { label: 'Ver inventario', onClick: () => navigate(`/inventario/${c.id}`) },
                            ...(permissions.write
                              ? [
                                  { label: 'Editar', onClick: () => navigate(`/convenios/${c.id}/editar`) },
                                  { divider: true },
                                  { label: c.estado ? 'Desactivar convenio' : 'Activar convenio', onClick: () => toggleEstado(c) },
                                  { label: 'Eliminar', danger: true, onClick: () => setConfirmTarget(c) },
                                ]
                              : []),
                          ]}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && (
          <Pagination page={page} totalPages={totalPages} onChange={setPage} totalLabel={`Mostrando ${pageRows.length} de ${total} convenios`} />
        )}
      </div>
      )}

      <Modal
        open={uploadOpen}
        onClose={() => { if (!uploading) { setUploadOpen(false); setUploadResult(null); } }}
        title="Cargar convenios"
        actions={<Button variant="secondary" onClick={() => { setUploadOpen(false); setUploadResult(null); }} disabled={uploading}>Cerrar</Button>}
      >
        <p style={{ marginTop: 0 }}>Archivo Excel o CSV con columnas: nombre, descripcion, precio_publico, precio_beet, fecha_inicio, fecha_fin, estado. Es un upsert: actualiza por nombre exacto si ya existe. Se envía a <code>POST /api/convenios/carga-masiva</code>.</p>
        {isSuperAdmin && selected && (
          <p className="text-caption" style={{ marginTop: -8, marginBottom: 12 }}>Estás gestionando datos de: <strong>{selected.nombre}</strong></p>
        )}
        <FileUploader hint="Excel o CSV · máx. 10 MB" onFile={handleUpload} />
        {uploading && <LoadingState title="Procesando archivo en el backend…" />}
        {!uploading && uploadResult && (
          <div style={{ marginTop: 16 }}>
            <Alert tone={uploadResult.invalidos > 0 ? 'error' : 'success'} title={uploadResult.detail}>
              {uploadResult.errores?.length > 0 && (
                <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                  {uploadResult.errores.slice(0, 10).map((e, i) => <li key={i}>{e}</li>)}
                  {uploadResult.errores.length > 10 && <li>…y {uploadResult.errores.length - 10} fila(s) más.</li>}
                </ul>
              )}
              {uploadResult.cambios?.length > 0 && (
                <>
                  <div className="text-caption" style={{ marginTop: 10, fontWeight: 600 }}>Qué cambió exactamente:</div>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                    {uploadResult.cambios.slice(0, 10).map((c, i) => <li key={i}>{c}</li>)}
                    {uploadResult.cambios.length > 10 && <li>…y {uploadResult.cambios.length - 10} cambio(s) más.</li>}
                  </ul>
                </>
              )}
            </Alert>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!confirmTarget}
        onClose={() => setConfirmTarget(null)}
        title={`¿Eliminar ${confirmTarget?.nombre}?`}
        description="Esta acción no elimina las transacciones ya registradas ni el inventario ya entregado. El convenio se marca como inactivo y desaparece del catálogo del afiliado (no hay borrado físico en la base de datos)."
        confirmLabel="Eliminar convenio"
        onConfirm={async () => {
          try {
            const actualizado = await convenioService.actualizarConvenio(confirmTarget.id, { estado: false });
            setConvenios((prev) => prev.map((c) => (c.id === confirmTarget.id ? actualizado : c)));
            push({ title: 'Convenio eliminado del catálogo', description: confirmTarget.nombre, variant: 'error' });
          } catch (err) {
            push({ title: 'No se pudo eliminar el convenio', description: err.message, variant: 'error' });
          } finally {
            setConfirmTarget(null);
          }
        }}
      />
    </div>
  );
}
