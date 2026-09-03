import { useEffect, useState } from 'react';
import * as convenioService from '../../services/convenioService';

// Renders the convenio's real branding image (its active plantilla's
// logo — see backend/app/routers/convenios.py) on top of a benefit card
// or the benefit detail header, or the pre-existing generic
// diagonal-stripes placeholder when `imagenMarcaUrl` is `null` (no
// plantilla/logo yet) or the fetch fails for any reason — the card must
// never look broken or empty either way.
export default function ConvenioImagenMarca({ imagenMarcaUrl, nombre, className = '', style }) {
  const [objectUrl, setObjectUrl] = useState(null);

  useEffect(() => {
    if (!imagenMarcaUrl) {
      setObjectUrl(null);
      return;
    }
    let url;
    let cancelado = false;
    convenioService
      .obtenerImagenMarcaBlob(imagenMarcaUrl)
      .then((blob) => {
        if (cancelado) return;
        url = URL.createObjectURL(blob);
        setObjectUrl(url);
      })
      .catch(() => {
        if (!cancelado) setObjectUrl(null);
      });
    return () => {
      cancelado = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [imagenMarcaUrl]);

  if (objectUrl) {
    return (
      <div className={`benefit-card-image benefit-card-image--photo ${className}`} style={style}>
        <img src={objectUrl} alt={nombre} />
      </div>
    );
  }

  return (
    <div className={`benefit-card-image ${className}`} style={style}>
      <span className="benefit-card-image-label">{nombre}</span>
    </div>
  );
}
