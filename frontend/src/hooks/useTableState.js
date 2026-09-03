import { useMemo, useState } from 'react';

// Small shared hook for the search + paginate pattern used by every list
// page (Convenios, Afiliados, Transacciones, Usuarios...).
export function useTableState({ data, searchFields = [], pageSize = 10, defaultFilters = {} }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(defaultFilters);

  const filtered = useMemo(() => {
    let rows = data;
    Object.entries(filters).forEach(([key, value]) => {
      // BUG FIX: `if (value)` treated `false` (a real, valid filter value —
      // e.g. estado=false for "Inactivos") as "no filter set", so filtering
      // by Inactivos silently showed every row instead of just the inactive
      // ones. Only "unset" (undefined or empty string, the "Todo estado"
      // option) should skip the filter — false/0 are legitimate values.
      if (value !== undefined && value !== '') rows = rows.filter((row) => String(row[key]) === String(value));
    });
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter((row) => searchFields.some((f) => String(row[f] ?? '').toLowerCase().includes(q)));
    }
    return rows;
  }, [data, search, filters, searchFields]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * pageSize, clampedPage * pageSize);

  return {
    search, setSearch: (v) => { setSearch(v); setPage(1); },
    filters, setFilter: (key, value) => { setFilters((f) => ({ ...f, [key]: value })); setPage(1); },
    page: clampedPage, setPage, totalPages, filtered, pageRows, total: filtered.length,
  };
}
