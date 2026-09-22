const BASE = '/api/v1'

function getToken(): string | null {
  try { return localStorage.getItem('sangam_token') } catch { return null }
}

export function setToken(token: string): void {
  try { localStorage.setItem('sangam_token', token) } catch {}
}

export function clearToken(): void {
  try { localStorage.removeItem('sangam_token') } catch {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.message || body.detail || res.statusText, body)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

// SSE subscription — returns a cleanup function
export function subscribeToRun(
  runId: string,
  onEvent: (event: import('@/types').FlowEvent) => void,
  onDone?: () => void,
): () => void {
  const es = new EventSource(`${BASE}/runs/${runId}/stream`)
  es.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data)
      onEvent(event)
      const terminal = ['run.completed', 'run.failed']
      if (terminal.includes(event.type)) {
        es.close()
        onDone?.()
      }
    } catch {}
  }
  es.onerror = () => { es.close(); onDone?.() }
  return () => es.close()
}
