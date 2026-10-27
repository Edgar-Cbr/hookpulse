import type {
  Endpoint,
  SimulatorTriggerRequest,
  SimulatorTriggerResponse,
  WebhookEvent,
} from '../types/webhook';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // Endpoints CRUD
  getEndpoints: (): Promise<Endpoint[]> => {
    return apiRequest<Endpoint[]>('/api/v1/endpoints');
  },

  createEndpoint: (data: { slug: string; name: string; target_url: string }): Promise<Endpoint> => {
    return apiRequest<Endpoint>('/api/v1/endpoints', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // Events & Delivery Attempts
  getEndpointEvents: (slug: string, limit: number = 50): Promise<WebhookEvent[]> => {
    return apiRequest<WebhookEvent[]>(`/api/v1/endpoints/${encodeURIComponent(slug)}/events?limit=${limit}`);
  },

  getEventDetail: (eventId: string): Promise<WebhookEvent> => {
    return apiRequest<WebhookEvent>(`/api/v1/events/${eventId}`);
  },

  replayEvent: (eventId: string): Promise<WebhookEvent> => {
    return apiRequest<WebhookEvent>(`/api/v1/events/${eventId}/replay`, {
      method: 'POST',
    });
  },

  // Simulator
  triggerSimulator: (data: SimulatorTriggerRequest): Promise<SimulatorTriggerResponse> => {
    return apiRequest<SimulatorTriggerResponse>('/api/v1/simulator/trigger', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // System Health
  getHealth: (): Promise<{ status: string; postgres: boolean; redis: boolean }> => {
    return apiRequest<{ status: string; postgres: boolean; redis: boolean }>('/health');
  },
};
