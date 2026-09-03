import { useEffect, useState } from 'react';
import { Input } from '../../components/ui/Field';
import { IconBuscar } from '../../components/ui/Icons';
import { SkeletonBlock, EmptyState, ErrorState } from '../../components/ui/States';
import { Card } from '../../components/ui/Card';
import BenefitCard from '../../components/portal/BenefitCard';
import * as convenioService from '../../services/convenioService';

// NOTE: unlike an earlier design assumption, the real `convenios` table has
// no `marca`/`categoria` columns — the brand/category filters that used to
// exist here were removed; only a free-text search over `nombre` remains
// (see ../../../SCHEMA_NOTES.md).
export default function Catalogo() {
  const [status, setStatus] = useState('loading'); // loading | success | error
  const [error, setError] = useState('');
  const [convenios, setConvenios] = useState([]);
  const [search, setSearch] = useState('');

  const cargar = () => {
    setStatus('loading');
    convenioService
      .obtenerCatalogoAfiliado()
      .then((data) => { setConvenios(data); setStatus('success'); })
      .catch((err) => { setError(err.message || 'No fue posible cargar la información.'); setStatus('error'); });
  };

  useEffect(() => { cargar(); }, []);

  const filtrados = convenios.filter((c) => {
    if (search.trim() && !c.nombre.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Catálogo de beneficios</h1>
          <p className="page-subtitle">Precio público, precio BEET y ahorro claramente diferenciados para cada convenio.</p>
        </div>
      </div>

      <Card padding="card-pad" className="section-gap">
        <label className="input-affix-wrap" style={{ maxWidth: 320 }}>
          <span className="input-affix-icon"><IconBuscar size={16} color="var(--text-muted)" /></span>
          <Input placeholder="Buscar beneficio" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </Card>

      {status === 'loading' && (
        <div className="grid grid-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <SkeletonBlock lines={[{ w: '40%', h: 12 }, { w: '80%', h: 20 }, { w: '55%', h: 24 }, { w: '60%', h: 10 }]} />
            </Card>
          ))}
        </div>
      )}

      {status === 'error' && <ErrorState description={error} onRetry={cargar} />}

      {status === 'success' && (
        filtrados.length === 0 ? (
          convenios.length === 0 ? (
            <EmptyState title="No hay convenios disponibles actualmente" description="Tu cooperativa todavía no ha habilitado convenios activos." />
          ) : (
            <EmptyState title="No encontramos beneficios con esos filtros" description="Ajusta la búsqueda para ver más resultados." />
          )
        ) : (
          <div className="grid grid-3">
            {filtrados.map((c) => (
              <BenefitCard key={c.id} convenio={c} />
            ))}
          </div>
        )
      )}
    </div>
  );
}
