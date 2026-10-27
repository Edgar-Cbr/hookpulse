export type WebhookStatus = 'PENDING' | 'DELIVERED' | 'RETRYING' | 'DLQ';

export interface DeliveryAttempt {
  id: number;
  event_id: string;
  attempt_number: number;
  response_status: number | null;
  response_body: string | null;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
}

export interface WebhookEvent {
  id: string;
  endpoint_id: string;
  event_type: string;
  headers: Record<string, any>;
  payload: Record<string, any>;
  signature_valid: boolean;
  status: WebhookStatus;
  retry_count: number;
  next_retry_at: string | null;
  created_at: string;
  attempts: DeliveryAttempt[];
}

export interface Endpoint {
  id: string;
  slug: string;
  name: string;
  target_url: string;
  signing_secret: string;
  is_active: boolean;
  created_at: string;
  event_count?: number;
  delivered_count?: number;
  retrying_count?: number;
  dlq_count?: number;
}

export interface SimulatorTriggerRequest {
  endpoint_slug: string;
  behavior: 'success' | 'fail';
  event_type: string;
  custom_payload?: Record<string, any>;
  sign_hmac: boolean;
}

export interface SimulatorTriggerResponse {
  event_id: string;
  status: WebhookStatus;
  event_type: string;
  behavior: string;
  target_url: string;
  signature_header?: string;
  message: string;
}

export interface WebSocketMessage {
  type: 'event.created' | 'event.updated' | 'pong';
  slug: string;
  event: WebhookEvent;
  latest_attempt?: DeliveryAttempt;
}
