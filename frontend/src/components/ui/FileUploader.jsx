import { useRef, useState } from 'react';
import { IconUpload } from './Icons';

export default function FileUploader({ label = 'Arrastra el archivo', hint = 'Excel o CSV · máx. 10 MB', accept = '.xlsx,.xls,.csv', onFile }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFiles = (files) => {
    if (files?.[0]) onFile?.(files[0]);
  };

  return (
    <div
      className={`dropzone ${dragging ? 'dragging' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
      role="button"
      tabIndex={0}
    >
      <IconUpload size={24} color="var(--brand-primary)" />
      <div style={{ fontSize: 14, fontWeight: 600, margin: '10px 0 4px' }}>{label}</div>
      <div className="text-caption">{hint}</div>
      <input ref={inputRef} type="file" accept={accept} onChange={(e) => handleFiles(e.target.files)} />
    </div>
  );
}
