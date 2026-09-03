import { useState } from 'react';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card } from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { Field, Input } from '../../../components/ui/Field';
import { Badge, StatusBadge } from '../../../components/ui/Badge';
import { IconBuscar, IconDescargar } from '../../../components/ui/Icons';
import { EmptyState } from '../../../components/ui/States';
import RequireCooperativaSeleccionada from '../../../components/layout/RequireCooperativaSeleccionada';
import * as documentosService from '../../../services/documentosService';
import { ApiError } from '../../../services/apiClient';
import { useToast } from '../../../context/ToastContext';
import { formatCOP, formatDate } from '../../../utils/format';

export default function DocumentosLegales() {
  useSetBreadcrumbs([{ label: 'Documentos legales' }]);
  const { push } = useToast();

  const [documento, setDocumento] = useState('');
  const [nombres, setNombres] = useState('');
  const [buscando, setBuscando] = useState(false);
  const [resultado, setResultado] = useState(null); // null = no search yet
  const [descargandoId, setDescargandoId] = useState(null);

  const buscar = async (e) => {
    e.preventDefault();
    if (!documento.trim()) return;
    setBuscando(true);
    try {
      const data = await documentosService.buscarDocumentosLegales({ documento: documento.trim(), nombres });
      setResultado(data);
    } catch (err) {
      push({ title: 'No se pudo realizar la búsqueda', description: err instanceof ApiError ? err.message : 'Intenta de nuevo.', variant: 'error' });
    } finally {
      setBuscando(false);
    }
  };

  const descargar = async (doc) => {
    setDescargandoId(doc.id);
    try {
      const blob = await documentosService.descargarDocumento(doc.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `documento-asuncion-deuda-${doc.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      push({ title: 'No se pudo descargar el documento', description: err.message, variant: 'error' });
    } finally {
      setDescargandoId(null);
    }
  };

  return (
    <RequireCooperativaSeleccionada>
      <div>
        <div className="page-header">
          <div>
            <h1 className="text-h1 page-title">Documentos legales</h1>
            <p className="page-subtitle">Soporte para disputas: consulta todos los documentos de asunción de deuda firmados por un afiliado.</p>
          </div>
        </div>

        <Card padding="card-pad-lg">
          <form onSubmit={buscar} className="grid grid-3" style={{ gap: 12, alignItems: 'end' }}>
            <Field label="Documento (cédula)" hint="Filtro principal — obligatorio.">
              <Input value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="1000000001" />
            </Field>
            <Field label="Nombres del afiliado" hint="Opcional — solo para confirmar visualmente, no filtra.">
              <Input value={nombres} onChange={(e) => setNombres(e.target.value)} placeholder="Juan Pérez" />
            </Field>
            <Button type="submit" icon={<IconBuscar size={16} />} loading={buscando} disabled={!documento.trim()}>Buscar</Button>
          </form>
        </Card>

        {resultado && (
          <Card padding="card-pad-lg" style={{ marginTop: 16 }}>
            {resultado.afiliado === null ? (
              <EmptyState
                title="No se encontró ningún afiliado"
                description="Ningún afiliado de esta cooperativa tiene ese número de documento."
              />
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600 }}>{resultado.afiliado.nombres} {resultado.afiliado.apellidos}</span>
                  <span className="text-small cell-muted">Documento: {resultado.afiliado.documento}</span>
                  {resultado.afiliado.nombre_coincide === false && (
                    <Badge tone="amber">El nombre ingresado no coincide con el registrado</Badge>
                  )}
                </div>

                {resultado.documentos.length === 0 ? (
                  <EmptyState title="Sin documentos" description="Este afiliado no tiene documentos de asunción de deuda registrados." />
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Convenio</th>
                          <th>Valor</th>
                          <th>Cuotas</th>
                          <th>Fecha generación</th>
                          <th>Fecha firma</th>
                          <th>Estado</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {resultado.documentos.map((doc) => (
                          <tr key={doc.id}>
                            <td>{doc.convenio_nombre}</td>
                            <td className="tabular">{formatCOP(doc.valor)}</td>
                            <td className="tabular">{doc.numero_cuotas ?? '—'}</td>
                            <td>{formatDate(doc.fecha_generacion)}</td>
                            <td>{doc.fecha_firma ? formatDate(doc.fecha_firma) : '—'}</td>
                            <td><StatusBadge status={doc.estado} /></td>
                            <td>
                              <Button
                                size="sm" variant="secondary" icon={<IconDescargar size={14} />}
                                loading={descargandoId === doc.id} onClick={() => descargar(doc)}
                              >
                                Descargar
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </Card>
        )}
      </div>
    </RequireCooperativaSeleccionada>
  );
}
