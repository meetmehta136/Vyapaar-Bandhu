import { useState, useEffect } from 'react';
import { getClients, getInvoices, getDashboardStats, getAlerts } from '@/lib/api';

function useAPI<T>(fetcher: () => Promise<T | null>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = () => {
    setLoading(true);
    setError(null);
    fetcher().then(d => {
      if (d !== null) {
        setData(d);
      } else {
        setError('Failed to load data. Check your connection.');
      }
      setLoading(false);
    });
  };

  useEffect(() => { fetch(); }, []);

  return { data, loading, error, refetch: fetch };
}

export function useClients() {
  return useAPI(getClients);
}

export function useInvoices() {
  return useAPI(getInvoices);
}

export function useDashboardStats() {
  return useAPI(getDashboardStats);
}

export function useAlerts() {
  return useAPI(getAlerts);
}