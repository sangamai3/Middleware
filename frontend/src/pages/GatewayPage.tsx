import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gatewayApi, type ApiProduct, type ApiKey } from '@/api/gateway'
import './GatewayPage.css'

export function GatewayPage() {
  const [tab, setTab] = useState<'products' | 'webhooks'>('products')
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null)

  return (
    <div className="gateway">
      <div className="gateway__header">
        <h1 className="gateway__title">API Gateway</h1>
        <div className="tab-bar">
          <button className={`tab${tab === 'products' ? ' tab--active' : ''}`} onClick={() => setTab('products')}>Products</button>
          <button className={`tab${tab === 'webhooks' ? ' tab--active' : ''}`} onClick={() => setTab('webhooks')}>Webhooks</button>
        </div>
      </div>

      {tab === 'products' && (
        selectedProduct
          ? <ProductDetail productId={selectedProduct} onBack={() => setSelectedProduct(null)} />
          : <ProductList onSelect={setSelectedProduct} />
      )}
      {tab === 'webhooks' && <WebhookList />}
    </div>
  )
}

// ── Product list ──────────────────────────────────────────────────────────────

function ProductList({ onSelect }: { onSelect: (id: string) => void }) {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [yaml, setYaml] = useState(DEFAULT_PRODUCT_YAML)

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['gateway-products'],
    queryFn: () => gatewayApi.listProducts(),
  })

  const createMutation = useMutation({
    mutationFn: (y: string) => gatewayApi.createProduct(y),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['gateway-products'] }); setShowCreate(false) },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteProduct(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gateway-products'] }),
  })

  return (
    <div className="gw-section">
      <div className="gw-section__head">
        <span className="gw-count">{products.length} product{products.length !== 1 ? 's' : ''}</span>
        <button className="btn btn--primary btn--sm" onClick={() => setShowCreate(true)}>+ Create Product</button>
      </div>

      {showCreate && (
        <div className="gw-create-card">
          <div className="gw-create-card__title">New API Product (YAML)</div>
          <textarea
            className="gw-yaml-editor"
            value={yaml}
            onChange={e => setYaml(e.target.value)}
            spellCheck={false}
          />
          {createMutation.error && (
            <div className="gw-error">{(createMutation.error as any).message}</div>
          )}
          <div className="gw-create-card__actions">
            <button className="btn btn--ghost btn--sm" onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn btn--primary btn--sm" onClick={() => createMutation.mutate(yaml)} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="gw-loading">Loading products…</div>
      ) : products.length === 0 ? (
        <div className="gw-empty">No API products yet. Create one above.</div>
      ) : (
        <div className="product-grid">
          {products.map((p: ApiProduct) => (
            <div key={p.product_id} className="product-card" onClick={() => onSelect(p.product_id)}>
              <div className="product-card__head">
                <div className="product-card__name">{p.name}</div>
                <span className={`pill${p.is_active ? ' pill--pass' : ' pill--muted'}`}>
                  {p.is_active ? 'active' : 'inactive'}
                </span>
              </div>
              <div className="product-card__id">{p.product_id}</div>
              <div className="product-card__meta">
                <span>v{p.version}</span>
                <span>{p.base_path}</span>
                <span>{p.endpoint_count ?? 0} endpoints</span>
              </div>
              <button
                className="product-card__delete"
                onClick={e => { e.stopPropagation(); deleteMutation.mutate(p.product_id) }}
              >Delete</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Product detail + keys + analytics ────────────────────────────────────────

function ProductDetail({ productId, onBack }: { productId: string; onBack: () => void }) {
  const qc = useQueryClient()
  const [showKey, setShowKey] = useState(false)
  const [newKeyForm, setNewKeyForm] = useState({ consumer_name: '', consumer_email: '', plan_name: 'free' })
  const [issuedKey, setIssuedKey] = useState<string | null>(null)

  const { data: keys = [] } = useQuery({
    queryKey: ['gateway-keys', productId],
    queryFn: () => gatewayApi.listKeys(productId),
  })

  const { data: analytics } = useQuery({
    queryKey: ['gateway-analytics', productId],
    queryFn: () => gatewayApi.getAnalytics(productId),
    retry: false,
  })

  const createKeyMutation = useMutation({
    mutationFn: () => gatewayApi.createKey(productId, newKeyForm),
    onSuccess: (result) => {
      setIssuedKey(result.plaintext_key || (result as any).key)
      qc.invalidateQueries({ queryKey: ['gateway-keys', productId] })
    },
  })

  const revokeKeyMutation = useMutation({
    mutationFn: (keyId: string) => gatewayApi.revokeKey(keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gateway-keys', productId] }),
  })

  return (
    <div className="gw-section">
      <button className="back-btn" onClick={onBack}>← Products</button>
      <h2 className="gw-detail-title">{productId}</h2>

      {analytics && (
        <div className="analytics-bar">
          <AnalyticsTile label="Requests" value={analytics.total_requests.toLocaleString()} />
          <AnalyticsTile label="Errors" value={`${(analytics.error_rate * 100).toFixed(1)}%`} />
          <AnalyticsTile label="p50" value={`${analytics.p50_ms.toFixed(0)}ms`} />
          <AnalyticsTile label="p95" value={`${analytics.p95_ms.toFixed(0)}ms`} />
          <AnalyticsTile label="p99" value={`${analytics.p99_ms.toFixed(0)}ms`} />
        </div>
      )}

      <div className="gw-section__head" style={{ marginTop: 20 }}>
        <span className="gw-count">{keys.length} API key{keys.length !== 1 ? 's' : ''}</span>
        <button className="btn btn--primary btn--sm" onClick={() => setShowKey(true)}>+ Issue Key</button>
      </div>

      {showKey && (
        <div className="gw-create-card">
          <div className="gw-create-card__title">Issue API Key</div>
          {issuedKey ? (
            <div className="key-issued">
              <div className="key-issued__label">Copy this key now — it will not be shown again.</div>
              <code className="key-issued__value">{issuedKey}</code>
              <button className="btn btn--ghost btn--sm" onClick={() => { setIssuedKey(null); setShowKey(false) }}>Done</button>
            </div>
          ) : (
            <>
              <div className="gw-form-row">
                <label>Consumer name</label>
                <input className="gw-input" value={newKeyForm.consumer_name} onChange={e => setNewKeyForm(f => ({ ...f, consumer_name: e.target.value }))} placeholder="acme-corp" />
              </div>
              <div className="gw-form-row">
                <label>Consumer email</label>
                <input className="gw-input" type="email" value={newKeyForm.consumer_email} onChange={e => setNewKeyForm(f => ({ ...f, consumer_email: e.target.value }))} placeholder="dev@acme.com" />
              </div>
              <div className="gw-form-row">
                <label>Plan</label>
                <input className="gw-input" value={newKeyForm.plan_name} onChange={e => setNewKeyForm(f => ({ ...f, plan_name: e.target.value }))} placeholder="free" />
              </div>
              <div className="gw-create-card__actions">
                <button className="btn btn--ghost btn--sm" onClick={() => setShowKey(false)}>Cancel</button>
                <button className="btn btn--primary btn--sm" onClick={() => createKeyMutation.mutate()} disabled={createKeyMutation.isPending}>
                  {createKeyMutation.isPending ? 'Issuing…' : 'Issue Key'}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <table className="dash-table" style={{ marginTop: 12 }}>
        <thead><tr><th>Consumer</th><th>Plan</th><th>Status</th><th>Last used</th><th></th></tr></thead>
        <tbody>
          {keys.map((k: ApiKey) => (
            <tr key={k.key_id}>
              <td><div style={{ fontWeight: 500 }}>{k.consumer_name}</div><div style={{ fontSize: 11, color: 'var(--color-muted)' }}>{k.consumer_email}</div></td>
              <td>{k.plan_name}</td>
              <td><span className={`pill${k.is_active ? ' pill--pass' : ' pill--muted'}`}>{k.is_active ? 'active' : 'revoked'}</span></td>
              <td style={{ fontSize: 12, color: 'var(--color-muted)' }}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'Never'}</td>
              <td>
                {k.is_active && (
                  <button className="link-btn link-btn--danger" onClick={() => revokeKeyMutation.mutate(k.key_id)}>Revoke</button>
                )}
              </td>
            </tr>
          ))}
          {keys.length === 0 && <tr><td colSpan={5} style={{ color: 'var(--color-muted)', textAlign: 'center', padding: 20 }}>No keys issued yet.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

function AnalyticsTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="analytics-tile">
      <div className="analytics-tile__value">{value}</div>
      <div className="analytics-tile__label">{label}</div>
    </div>
  )
}

// ── Webhook list ─────────────────────────────────────────────────────────────

function WebhookList() {
  const qc = useQueryClient()
  const { data: webhooks = [] } = useQuery({
    queryKey: ['webhooks'],
    queryFn: () => gatewayApi.listWebhooks(),
    retry: false,
  })

  const deleteMutation = useMutation({
    mutationFn: (subId: string) => gatewayApi.deleteWebhook(subId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  })

  return (
    <div className="gw-section">
      <div className="gw-section__head">
        <span className="gw-count">{webhooks.length} webhook{webhooks.length !== 1 ? 's' : ''}</span>
      </div>
      <table className="dash-table">
        <thead><tr><th>Consumer</th><th>URL</th><th>Events</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {webhooks.map((w: any) => (
            <tr key={w.sub_id}>
              <td style={{ fontWeight: 500 }}>{w.consumer_name}</td>
              <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{w.url}</td>
              <td style={{ fontSize: 12 }}>{w.events.join(', ')}</td>
              <td><span className={`pill${w.is_active ? ' pill--pass' : ' pill--muted'}`}>{w.is_active ? 'active' : 'inactive'}</span></td>
              <td><button className="link-btn link-btn--danger" onClick={() => deleteMutation.mutate(w.sub_id)}>Delete</button></td>
            </tr>
          ))}
          {webhooks.length === 0 && <tr><td colSpan={5} style={{ color: 'var(--color-muted)', textAlign: 'center', padding: 20 }}>No webhooks registered.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

const DEFAULT_PRODUCT_YAML = `product_id: my-api
name: My API
version: "1.0"
base_path: /my-api
endpoints:
  - path: /data
    method: GET
    flow_id: my-flow
    auth: api_key
    mock_response:
      status_code: 200
      body: {message: "Hello from My API"}
plans:
  - name: free
    requests_per_day: 1000
    requests_per_minute: 60
`
