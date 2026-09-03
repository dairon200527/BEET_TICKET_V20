import { useEffect, useRef, useState } from 'react';
import Button from './Button';

// Signature capture — draws to a canvas and, once the stroke ends, reports
// the drawing as a base64-encoded PNG (no `data:` prefix) via
// onChange(base64PngOrNull). This is the actual payload the backend's
// purchase endpoint expects as `firma_base64` for cupo purchases (see
// backend/app/services/transaction_service.py) — the canvas itself is
// still not a legally-binding signature on its own; the backend is what
// turns it into the signed debt-assumption document.
export default function SignaturePad({ onChange }) {
  const canvasRef = useRef(null);
  const drawingRef = useRef(false);
  const [hasSignature, setHasSignature] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const ratio = window.devicePixelRatio || 1;
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.2;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#1C26E5';
  }, []);

  const pointerPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const start = (e) => {
    drawingRef.current = true;
    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = pointerPos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };
  const move = (e) => {
    if (!drawingRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = pointerPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    if (!hasSignature) setHasSignature(true);
  };
  const stop = () => {
    if (drawingRef.current && hasSignature) {
      const dataUrl = canvasRef.current.toDataURL('image/png');
      onChange?.(dataUrl.split(',')[1]); // strip the "data:image/png;base64," prefix
    }
    drawingRef.current = false;
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
    onChange?.(null);
  };

  return (
    <div>
      <canvas
        ref={canvasRef}
        className="signature-canvas"
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={stop}
        onPointerLeave={stop}
      />
      <div className="signature-footer">
        <span className="text-caption">{hasSignature ? 'Firma capturada' : 'Firma dentro del recuadro con el mouse o el dedo'}</span>
        <Button size="sm" variant="secondary" type="button" onClick={clear}>Limpiar</Button>
      </div>
    </div>
  );
}
