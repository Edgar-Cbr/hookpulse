import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import type { WebhookEvent, WebSocketMessage } from '../types/webhook';

interface UseWebhookStreamOptions {
  slug: string;
  autoConnect?: boolean;
}

interface UseWebhookStreamResult {
  events: WebhookEvent[];
  selectedEvent: WebhookEvent | null;
  setSelectedEvent: (event: WebhookEvent | null) => void;
  isConnected: boolean;
  isReconnecting: boolean;
  isLoading: boolean;
  error: string | null;
  replayEvent: (eventId: string) => Promise<void>;
  refreshEvents: () => Promise<void>;
}

export function useWebhookStream({
  slug,
  autoConnect = true,
}: UseWebhookStreamOptions): UseWebhookStreamResult {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<WebhookEvent | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const pingIntervalRef = useRef<number | null>(null);
  const isMountedRef = useRef<boolean>(true);

  // 1. Initial REST fetch for event history
  const refreshEvents = useCallback(async () => {
    if (!slug) return;
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.getEndpointEvents(slug, 50);
      if (isMountedRef.current) {
        setEvents(data);
        if (data.length > 0 && !selectedEvent) {
          setSelectedEvent(data[0]);
        }
      }
    } catch (err: any) {
      if (isMountedRef.current) {
        setError(err.message || 'Failed to load events');
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [slug, selectedEvent]);

  // 2. Manual Replay Trigger
  const replayEvent = useCallback(
    async (eventId: string) => {
      try {
        setError(null);
        const updated = await api.replayEvent(eventId);
        setEvents((prev) =>
          prev.map((e) => (e.id === updated.id ? updated : e))
        );
        setSelectedEvent((curr) => (curr?.id === updated.id ? updated : curr));
      } catch (err: any) {
        setError(err.message || 'Replay failed');
        throw err;
      }
    },
    []
  );

  // 3. WebSocket Connection & Auto-reconnect
  const connectWebSocket = useCallback(() => {
    if (!slug || !autoConnect) return;

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/endpoints/${encodeURIComponent(slug)}`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);
        setIsReconnecting(false);
        setError(null);
        reconnectAttemptsRef.current = 0;

        // Keep-alive ping every 25s
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!isMountedRef.current) return;
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);

          if (msg.type === 'event.created') {
            setEvents((prev) => {
              // Avoid duplicates if already present
              const exists = prev.some((e) => e.id === msg.event.id);
              if (exists) return prev;
              return [msg.event, ...prev.slice(0, 49)];
            });
            setSelectedEvent((curr) => (!curr ? msg.event : curr));
          } else if (msg.type === 'event.updated') {
            setEvents((prev) =>
              prev.map((item) => (item.id === msg.event.id ? msg.event : item))
            );
            setSelectedEvent((curr) =>
              curr?.id === msg.event.id ? msg.event : curr
            );
          }
        } catch {
          // ignore pong / non-json messages
        }
      };

      ws.onerror = () => {
        // Handled in onclose
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setIsConnected(false);
        if (pingIntervalRef.current) {
          window.clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Schedule auto-reconnect with exponential backoff capped at 10s
        const attempt = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(1.5, attempt), 10000);
        reconnectAttemptsRef.current += 1;
        setIsReconnecting(true);

        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (isMountedRef.current) {
            connectWebSocket();
          }
        }, delay);
      };
    } catch (err: any) {
      if (isMountedRef.current) {
        setIsConnected(false);
        setIsReconnecting(true);
      }
    }
  }, [slug, autoConnect]);

  // 4. Lifecycle effect
  useEffect(() => {
    isMountedRef.current = true;
    refreshEvents();
    connectWebSocket();

    return () => {
      isMountedRef.current = false;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        window.clearInterval(pingIntervalRef.current);
      }
    };
  }, [slug, refreshEvents, connectWebSocket]);

  return {
    events,
    selectedEvent,
    setSelectedEvent,
    isConnected,
    isReconnecting,
    isLoading,
    error,
    replayEvent,
    refreshEvents,
  };
}
