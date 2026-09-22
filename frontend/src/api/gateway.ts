import { api } from './client'

export interface ApiProduct {
  product_id: string
  name: string
  version: string
  base_path: string
  is_active: boolean
  portal_enabled: boolean
  endpoint_count: number
}

export interface ApiKey {
  key_id: string
  consumer_name: string
  consumer_email: string
  plan_name: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
}

export interface CreateKeyRequest {
  consumer_name: string
  consumer_email: string
  plan_name: string
}

export interface GatewayAnalytics {
  product_id: string
  total_requests: number
  error_count: number
  error_rate: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  top_consumers: { consumer_key: string; request_count: number }[]
  endpoints: {
    path: string
    method: string
    requests: number
    errors: number
    p95_ms: number
  }[]
}

export interface WebhookSubscription {
  sub_id: string
  consumer_name: string
  url: string
  events: string[]
  is_active: boolean
  created_at: string
}

export const gatewayApi = {
  listProducts: () => api.get<ApiProduct[]>('/gateway/products'),
  getProduct: (id: string) => api.get<ApiProduct>(`/gateway/products/${id}`),
  createProduct: (yamlContent: string) =>
    api.post<ApiProduct>('/gateway/products', { yaml_content: yamlContent }),
  deleteProduct: (id: string) => api.delete<void>(`/gateway/products/${id}`),

  listKeys: (productId: string) => api.get<ApiKey[]>(`/gateway/products/${productId}/keys`),
  createKey: (productId: string, req: CreateKeyRequest) =>
    api.post<{ plaintext_key: string } & ApiKey>(`/gateway/products/${productId}/keys`, req),
  revokeKey: (keyId: string) => api.delete<void>(`/gateway/keys/${keyId}`),

  getAnalytics: (productId: string) =>
    api.get<GatewayAnalytics>(`/gateway/products/${productId}/analytics`),
  getSummary: () => api.get<{ total_products: number; total_requests: number; error_rate: number }>(
    '/gateway/analytics/summary'
  ),

  listWebhooks: () => api.get<WebhookSubscription[]>('/webhooks'),
  deleteWebhook: (subId: string) => api.delete<void>(`/webhooks/${subId}`),
}
