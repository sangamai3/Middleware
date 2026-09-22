import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi, type AlertRule, type AlertTrigger, type AlertChannel } from '@/api/notifications'
import './NotificationsPage.css'

const TRIGGER_LABELS: Record<AlertTrigger, string> = {
  flow_failed: 'Flow failed',
  flow_slow: 'Flow slow',
  error_rate_high: 'High error rate',
  run_started: 'Run started',
  run_completed: 'Run completed',
}

const TRIGGER_DESCS: Record<AlertTrigger, string> = {
  flow_failed: 'Fires when a flow execution fails',
  flow_slow: 'Fires when a run exceeds a duration threshold',
  error_rate_high: 'Fires when the error rate exceeds a threshold',
  run_started: 'Fires when any run starts',
  run_completed: 'Fires when any run completes successfully',
}

export function NotificationsPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [testResult, setTestResult] = useState<Record<string, boolean>>({})

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ['alert-rules'],
    queryFn: () => notificationsApi.listRules(),
    retry: false,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.deleteRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alert-rules'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      notificationsApi.updateRule(id, { is_active: active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alert-rules'] }),
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.testRule(id),
    onSuccess: (result, id) => setTestResult(r => ({ ...r, [id]: result.fired })),
  })

  return (
    <div className="notifications">
      <div className="notifications__header">
        <div>
          <h1 className="notifications__title">Notifications</h1>
          <p className="notifications__sub">Alert rules that fire on flow events via Slack or webhook.</p>
        </div>
        <button className="notif-btn notif-btn--primary" onClick={() => setShowCreate(true)}>
          + Create rule
        </button>
      </div>

      {showCreate && (
        <CreateRuleForm
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ['alert-rules'] }) }}
        />
      )}

      {isLoading ? (
        <div className="notif-loading">Loading rules…</div>
      ) : rules.length === 0 && !showCreate ? (
        <div className="notif-empty">
          <div className="notif-empty__icon">🔔</div>
          <div className="notif-empty__text">No alert rules yet. Create one to get notified when flows fail.</div>
        </div>
      ) : (
        <div className="rules-list">
          {rules.map((rule: AlertRule) => (
            <div key={rule.rule_id} className={`rule-card${rule.is_active ? '' : ' rule-card--inactive'}`}>
              <div className="rule-card__head">
                <div className="rule-card__name">{rule.name}</div>
                <div className="rule-card__actions">
                  {testResult[rule.rule_id] !== undefined && (
                    <span className={`test-badge${testResult[rule.rule_id] ? ' test-badge--ok' : ' test-badge--fail'}`}>
                      {testResult[rule.rule_id] ? '✓ sent' : '✗ failed'}
                    </span>
                  )}
                  <button
                    className="notif-btn notif-btn--ghost notif-btn--sm"
                    onClick={() => testMutation.mutate(rule.rule_id)}
                    disabled={testMutation.isPending}
                  >Test</button>
                  <button
                    className="notif-btn notif-btn--ghost notif-btn--sm"
                    onClick={() => toggleMutation.mutate({ id: rule.rule_id, active: !rule.is_active })}
                  >{rule.is_active ? 'Disable' : 'Enable'}</button>
                  <button
                    className="notif-btn notif-btn--danger notif-btn--sm"
                    onClick={() => deleteMutation.mutate(rule.rule_id)}
                  >Delete</button>
                </div>
              </div>

              <div className="rule-card__body">
                <div className="rule-meta">
                  <span className="trigger-badge">{TRIGGER_LABELS[rule.trigger as AlertTrigger] ?? rule.trigger}</span>
                  <span className="rule-desc">{TRIGGER_DESCS[rule.trigger as AlertTrigger]}</span>
                </div>
                {rule.flow_ids && (
                  <div className="rule-flows">
                    Flows: {rule.flow_ids.join(', ')}
                  </div>
                )}
                {rule.conditions && Object.keys(rule.conditions).length > 0 && (
                  <div className="rule-conditions">
                    Conditions: {JSON.stringify(rule.conditions)}
                  </div>
                )}
                <div className="channels-row">
                  {rule.channels.map((ch, i) => (
                    <ChannelChip key={i} channel={ch} />
                  ))}
                  {rule.channels.length === 0 && (
                    <span className="rule-no-channels">No channels configured — rule will not fire.</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ChannelChip({ channel }: { channel: AlertChannel }) {
  const isSlack = channel.channel_type === 'slack'
  return (
    <span className="channel-chip">
      {isSlack ? '💬 Slack' : '🔗 Webhook'}
    </span>
  )
}

// ── Create rule form ──────────────────────────────────────────────────────────

const TRIGGERS: AlertTrigger[] = ['flow_failed', 'flow_slow', 'error_rate_high', 'run_started', 'run_completed']

function CreateRuleForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [trigger, setTrigger] = useState<AlertTrigger>('flow_failed')
  const [flowIds, setFlowIds] = useState('')
  const [thresholdMs, setThresholdMs] = useState('30000')
  const [errorRate, setErrorRate] = useState('0.1')
  const [channelType, setChannelType] = useState<'slack' | 'webhook'>('slack')
  const [slackUrl, setSlackUrl] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')

  const mutation = useMutation({
    mutationFn: () => {
      const channels: AlertChannel[] = []
      if (channelType === 'slack' && slackUrl) {
        channels.push({ channel_type: 'slack', webhook_url: slackUrl })
      }
      if (channelType === 'webhook' && webhookUrl) {
        channels.push({ channel_type: 'webhook', url: webhookUrl, secret: webhookSecret })
      }
      const conditions: Record<string, unknown> = {}
      if (trigger === 'flow_slow') conditions.threshold_ms = parseInt(thresholdMs, 10)
      if (trigger === 'error_rate_high') conditions.error_rate_threshold = parseFloat(errorRate)

      return notificationsApi.createRule({
        name,
        trigger,
        flow_ids: flowIds.trim() ? flowIds.split(',').map(s => s.trim()).filter(Boolean) : null,
        conditions,
        channels,
      })
    },
    onSuccess: onCreated,
  })

  return (
    <div className="create-rule-card">
      <div className="create-rule-card__head">
        <span className="create-rule-card__title">New Alert Rule</span>
        <button className="create-rule-card__close" onClick={onClose}>×</button>
      </div>

      <div className="create-rule-body">
        <div className="cr-row">
          <label>Rule name</label>
          <input className="cr-input" value={name} onChange={e => setName(e.target.value)} placeholder="Notify on failure" />
        </div>

        <div className="cr-row">
          <label>Trigger</label>
          <select className="cr-select" value={trigger} onChange={e => setTrigger(e.target.value as AlertTrigger)}>
            {TRIGGERS.map(t => <option key={t} value={t}>{TRIGGER_LABELS[t]}</option>)}
          </select>
          <div className="cr-hint">{TRIGGER_DESCS[trigger]}</div>
        </div>

        {trigger === 'flow_slow' && (
          <div className="cr-row">
            <label>Threshold (ms)</label>
            <input className="cr-input" type="number" value={thresholdMs} onChange={e => setThresholdMs(e.target.value)} />
          </div>
        )}
        {trigger === 'error_rate_high' && (
          <div className="cr-row">
            <label>Error rate threshold (0–1)</label>
            <input className="cr-input" type="number" step="0.01" value={errorRate} onChange={e => setErrorRate(e.target.value)} />
          </div>
        )}

        <div className="cr-row">
          <label>Flows (optional, comma-separated IDs)</label>
          <input className="cr-input" value={flowIds} onChange={e => setFlowIds(e.target.value)} placeholder="flow-a, flow-b (leave blank for all)" />
        </div>

        <div className="cr-row">
          <label>Channel type</label>
          <div className="cr-toggle">
            <button className={`cr-toggle-btn${channelType === 'slack' ? ' cr-toggle-btn--active' : ''}`} onClick={() => setChannelType('slack')}>Slack</button>
            <button className={`cr-toggle-btn${channelType === 'webhook' ? ' cr-toggle-btn--active' : ''}`} onClick={() => setChannelType('webhook')}>Webhook</button>
          </div>
        </div>

        {channelType === 'slack' && (
          <div className="cr-row">
            <label>Slack Incoming Webhook URL</label>
            <input className="cr-input" type="url" value={slackUrl} onChange={e => setSlackUrl(e.target.value)} placeholder="https://hooks.slack.com/services/…" />
          </div>
        )}

        {channelType === 'webhook' && (
          <>
            <div className="cr-row">
              <label>Webhook URL</label>
              <input className="cr-input" type="url" value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)} placeholder="https://my-service.com/hooks/sangam" />
            </div>
            <div className="cr-row">
              <label>HMAC secret (optional)</label>
              <input className="cr-input" type="password" value={webhookSecret} onChange={e => setWebhookSecret(e.target.value)} placeholder="secret for X-SangamMW-Signature" />
            </div>
          </>
        )}

        {mutation.error && (
          <div className="cr-error">{(mutation.error as any).message}</div>
        )}

        <div className="cr-actions">
          <button className="notif-btn notif-btn--ghost" onClick={onClose}>Cancel</button>
          <button className="notif-btn notif-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending || !name.trim()}>
            {mutation.isPending ? 'Creating…' : 'Create rule'}
          </button>
        </div>
      </div>
    </div>
  )
}
