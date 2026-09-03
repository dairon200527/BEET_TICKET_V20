import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const BreadcrumbContext = createContext(null);

export function BreadcrumbProvider({ children }) {
  const [items, setItems] = useState([{ label: 'Dashboard' }]);
  const value = useMemo(() => ({ items, setItems }), [items]);
  return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>;
}

// Call from a page to set the breadcrumb trail for as long as it's mounted.
export function useSetBreadcrumbs(items) {
  const ctx = useContext(BreadcrumbContext);
  const key = JSON.stringify(items);
  useEffect(() => {
    ctx.setItems(items);
    return () => ctx.setItems([{ label: 'Dashboard' }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

export function useBreadcrumbs() {
  const ctx = useContext(BreadcrumbContext);
  return ctx.items;
}
