// app/StoreProvider.tsx
'use client';
import { useEffect, useState } from 'react';
import { Provider } from 'react-redux';
import { makeStore, type AppStore } from './store';

export default function StoreProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [store, setStore] = useState<AppStore | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setStore(makeStore()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (!store) return null;

  return <Provider store={store}>{children}</Provider>;
}
