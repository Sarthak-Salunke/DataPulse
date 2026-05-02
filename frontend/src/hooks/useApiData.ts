// src/hooks/useApiData.ts
// Data-fetching hooks powered by TanStack React Query v5.
//
// What changed vs. the old implementation:
//   - Replaced manual setInterval + useState with useQuery.
//   - Polling now pauses automatically when the browser tab is hidden
//     (refetchIntervalInBackground: false on the QueryClient default).
//   - Multiple components that call the same hook share one in-flight
//     request and one cached result — no duplicate network calls.
//   - Return shapes are identical to the old hooks so Dashboard.tsx
//     requires no changes at all.
//
// The WebSocket hook (useWebSocket) is unchanged — React Query is for
// REST polling only; real-time push is still handled by the native
// WebSocket API.

import { useQuery } from '@tanstack/react-query';
import { useState, useEffect, useCallback, useRef } from 'react';

// Re-export the canonical types from types/index.ts so any file that
// currently imports them from here continues to work without modification.
export type { DashboardMetrics, FraudAlert, Transaction } from '../types';
import type { DashboardMetrics, FraudAlert, Transaction } from '../types';

// ============================================================================
// Shared fetch helper
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000/ws';

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',   // send the httpOnly auth cookie automatically
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ============================================================================
// Query key factory — centralised so keys never drift between hooks
// ============================================================================

export const queryKeys = {
  dashboardMetrics: ['dashboard', 'metrics'] as const,
  fraudAlerts: (limit: number) => ['fraud', 'alerts', limit] as const,
  transactions: (limit: number) => ['transactions', limit] as const,
  health: ['health'] as const,
};

// ============================================================================
// Hook: Dashboard Metrics
// ============================================================================

export function useDashboardMetrics(refreshInterval = 5000) {
  const { data: metrics = null, isLoading: loading, error, refetch: refresh } = useQuery({
    queryKey: queryKeys.dashboardMetrics,
    queryFn: () => apiFetch<DashboardMetrics>('/api/dashboard/metrics'),
    refetchInterval: refreshInterval,
    // Each call site can override the interval by passing a different value,
    // but the background-pause behaviour is always active (set on QueryClient).
  });

  return {
    metrics,
    loading,
    error: error ? (error as Error).message : null,
    refresh,
  };
}

// ============================================================================
// Hook: Recent Fraud Alerts
// ============================================================================

export function useRecentAlerts(limit = 10, refreshInterval = 3000) {
  const { data: alerts = [], isLoading: loading, error, refetch: refresh } = useQuery({
    queryKey: queryKeys.fraudAlerts(limit),
    queryFn: () => apiFetch<FraudAlert[]>(`/api/fraud/alerts?limit=${limit}`),
    refetchInterval: refreshInterval,
  });

  return {
    alerts,
    loading,
    error: error ? (error as Error).message : null,
    refresh,
  };
}

// ============================================================================
// Hook: All Transactions
// ============================================================================

export function useTransactions(limit = 50, refreshInterval = 5000) {
  const { data: transactions = [], isLoading: loading, error, refetch: refresh } = useQuery({
    queryKey: queryKeys.transactions(limit),
    queryFn: () => apiFetch<Transaction[]>(`/api/transactions?limit=${limit}`),
    refetchInterval: refreshInterval,
  });

  return {
    transactions,
    loading,
    error: error ? (error as Error).message : null,
    refresh,
  };
}

// ============================================================================
// Hook: Health Check
// ============================================================================

export function useHealthCheck(checkInterval = 30000) {
  const { data, refetch: check } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiFetch<{ status: string; time: string }>('/api/health'),
    refetchInterval: checkInterval,
  });

  return {
    healthy: data ? data.status === 'healthy' : null,
    lastCheck: data?.time ?? null,
    check,
  };
}

// ============================================================================
// Hook: WebSocket Connection for Real-time Updates
// — unchanged from original implementation —
// ============================================================================

interface WebSocketMessage {
  type: string;
  data?: unknown;
  message?: string;
  timestamp?: string;
}

export function useWebSocket(onMessage?: (message: WebSocketMessage) => void) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    try {
      console.log('🔌 Connecting to WebSocket:', WS_URL);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket connected');
        setConnected(true);
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string) as WebSocketMessage;
          setLastMessage(message);
          onMessage?.(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        setConnected(false);
        wsRef.current = null;

        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          console.log(`⏱️  Reconnecting in ${delay / 1000}s… (${reconnectAttempts.current}/${maxReconnectAttempts})`);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        } else {
          console.error('❌ Max reconnection attempts reached');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [onMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { connected, lastMessage, sendMessage, reconnect: connect, disconnect };
}
