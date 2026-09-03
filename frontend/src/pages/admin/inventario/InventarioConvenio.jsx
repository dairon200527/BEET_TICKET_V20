import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card } from '../../../components/ui/Card';
import { Tabs, Pagination } from '../../../components/ui/Nav';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import FileUploader from '../../../components/ui/FileUploader';
import Alert from '../../../components/ui/Alert';
import PermissionGate from '../../../components/ui/PermissionGate';
import { IconDescargar } from '../../../components/ui/Icons';
import * as convenioService from '../../../services/convenioService';
import * as inventarioService from '../../../services/inventarioService';
import { formatDate } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';

const TABS = [
  { key: 'disponible', label: 'Disponibles' },
  { key: 'entregada', label: 'Entregadas' },
  { key: 'vencida', label: 'Vencidas' },
  { key: '', label: 'Todo el historial' },
];

export default function InventarioConvenio() {
  const { convenioId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();

  const [convenio, setConvenio] = useState(null);
  const [loadingConvenio, setLoadingConvenio] = useState(true);

  const [tab, setTab] = useState('disponible');
  const [page, setPage] = useState(1);
  const [unidades, setUnidades] = useState({ items: [], total: 0, page: 1, page_size: 8 });
  const [loadingUnidades, setLoadingUnidades] = useState(true);
  const [error, setError] = useState(null);

  const [uploadState, setUploadState] = useState(null); // { fileName, status, message }
  const [uploading, setUploading] = useState(false);

  useSetBreadcrumbs([
    { label: 'Inventario', to: '/inventario' },
    { label: convenio?.nombre ?? 'Detalle' },
  ]);

  useEffect(() => {
    setLoadingConvenio(true);
    convenioService
      .obtenerConvenio(convenioId)
      .then(setConvenio)
      .catch(() => setConvenio(null))
      .finally(() => setLoadingConvenio(false));
  }, [convenioId]);

  const cargarUnidades = useCallback(() => {
    setLoadingUnidades(true);
    setError(null);
    inventarioService
      .listarInventario(convenioId, { estado: tab || undefined, page, pageSize: 8 })
      .then(setUnidades)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingUnidades(false));
  }, [convenioId, tab, page]);

  useEffect(() => { cargarUnidades(); }, [cargarUnidades]);

  if (loadingConvenio) return <LoadingState title="Cargando convenio…" />;
  if (!convenio) {
    return <EmptyState title="Convenio no encontrado" actionLabel="Volver a inventario" onAction={() => navigate('/inventario')} />;
  }

  const handleFile = async (file) => {
    const isCsvOrXlsx = /\.(csv|xlsx|xls)$/i.test(file.name);
    if (!isCsvOrXlsx) {
      setUploadState({ fileName: file.name, status: 'error', message: 'Formato no soportado. Usa Excel (.xlsx) o CSV.', errores: [] });
      return;
    }
    setUploading(true);
    try {
      const result = await inventarioService.cargaInventario(convenioId, file);
      // A 200 response only means the file was PROCESSED — invalid/duplicate
      // rows still happened, so the box color reflects that instead of
      // always claiming unconditional success.
      const tieneProblemas = result.invalidos > 0 || result.omitidos > 0;
      setUploadState({ fileName: file.name, status: tieneProblemas ? 'error' : 'success', message: result.detail, errores: result.errores ?? [] });
      push({
        title: tieneProblemas ? 'Carga procesada con filas inválidas o duplicadas' : 'Inventario cargado correctamente',
        description: result.detail,
        variant: tieneProblemas ? 'error' : 'success',
      });
      setPage(1);
      cargarUnidades();
    } catch (err) {
      setUploadState({ fileName: file.name, status: 'error', message: err.message, errores: [] });
      push({ title: 'No se pudo cargar el inventario', description: err.message, variant: 'error' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">{convenio.nombre}</h1>
          <p className="page-subtitle">Agrega nuevos lotes de códigos a este convenio sin afectar el inventario que ya tienes cargado.</p>
        </div>
        <div className="page-header-actions">
          <Button variant="secondary" icon={<IconDescargar size={15} color="#1F2937" />}>Descargar detalle de códigos</Button>
        </div>
      </div>

      <PermissionGate>
        <Card padding="card-pad-lg" className="section-gap">
          <div className="text-label" style={{ marginBottom: 14 }}>+ Agregar inventario</div>
          <div className="grid grid-2">
            <FileUploader label="Arrastra el nuevo lote de códigos" hint="Excel o CSV con columna: codigo · máx. 10 MB" onFile={handleFile} />
            {uploading ? (
              <LoadingState title="Procesando archivo en el backend…" />
            ) : uploadState && (
              <Alert tone={uploadState.status} title={uploadState.fileName}>
                {uploadState.message}
                {uploadState.errores?.length > 0 && (
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                    {uploadState.errores.slice(0, 10).map((e, i) => <li key={i}>{e}</li>)}
                    {uploadState.errores.length > 10 && <li>…y {uploadState.errores.length - 10} fila(s) más.</li>}
                  </ul>
                )}
              </Alert>
            )}
          </div>
          <Alert tone="info" title="El inventario existente nunca se borra">
            Cada carga solo AGREGA los códigos nuevos del archivo — los que ya tenías cargados no se tocan.
            Un código repetido (el mismo código ya existe) se detecta y se reporta como duplicado, no se
            crea dos veces. La plantilla visual del ticket se administra por separado, desde el detalle del convenio.
          </Alert>
        </Card>
      </PermissionGate>

      <Card padding="card-pad-lg">
        <Tabs items={TABS} active={tab} onChange={(k) => { setTab(k); setPage(1); }} />
        <div style={{ marginTop: 18 }}>
          {loadingUnidades ? (
            <LoadingState title="Cargando unidades…" />
          ) : error ? (
            <ErrorState description={error} onRetry={cargarUnidades} />
          ) : unidades.items.length === 0 ? (
            <EmptyState title="No hay unidades en este estado" description="Cuando se cargue o consuma inventario, aparecerá aquí." />
          ) : (
            <>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Estado</th>
                      <th>Fecha de ingreso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unidades.items.map((u) => (
                      <tr key={u.id}>
                        <td className="text-mono">{u.codigo}</td>
                        <td><StatusBadge status={u.estado} /></td>
                        <td className="text-small">{formatDate(u.fecha_ingreso)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={unidades.page}
                totalPages={Math.max(1, Math.ceil(unidades.total / unidades.page_size))}
                onChange={setPage}
                totalLabel={`Mostrando ${unidades.items.length} de ${unidades.total} unidades`}
              />
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
