// ─── Connector types ────────────────────────────────────────────────
export interface ConnectorMeta {
  connector_id: string
  label: string
  family: string
  version: string
  auth_type: string
  operations: string[]
  description: string
  connection_schema?: JSONSchema
  read_schema?: JSONSchema
  write_schema?: JSONSchema
}

export interface JSONSchema {
  type: string
  properties?: Record<string, JSONSchemaProperty>
  required?: string[]
}

export interface JSONSchemaProperty {
  type: string
  description?: string
  enum?: string[]
  default?: unknown
  secret?: boolean
}

export interface ObjectSchema {
  name: string
  kind: string
  description?: string
}

export interface ColumnSchema {
  name: string
  data_type: string
  nullable?: boolean
  is_primary_key?: boolean
  description?: string
}

// ─── Connection ─────────────────────────────────────────────────────
export interface Connection {
  connection_id: string
  name: string
  connector_id: string
  status: 'active' | 'error' | 'untested'
}

// ─── Flow types ──────────────────────────────────────────────────────
export type FlowStatus = 'draft' | 'deployed' | 'paused' | 'archived'
export type TriggerType = 'manual' | 'scheduled' | 'webhook' | 'streaming' | 'api'

export interface StepConfig {
  id: string
  type: string
  config: Record<string, unknown>
  depends_on: string[]
  retries: number
  retry_delay: string
  retry_on: string[]
  timeout_seconds: number | null
  on_row_error: string
  optional: boolean
}

export interface FlowDefinition {
  flow_id: string
  name: string
  description: string
  version: string
  status: FlowStatus
  trigger: TriggerType
  trigger_config: Record<string, unknown>
  steps: StepConfig[]
  variables: Record<string, unknown>
  tags: string[]
  created_at?: string
  updated_at?: string
  created_by: string
}

// ─── Execution types ─────────────────────────────────────────────────
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'timed_out' | 'cancelled'
export type StepStatus = 'pending' | 'running' | 'success' | 'failed' | 'retrying' | 'skipped'

export interface StepExecution {
  step_id: string
  step_type: string
  step_label?: string
  connector_id?: string | null
  status: StepStatus
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  rows_in: number
  rows_out: number
  rows_failed: number
  error_type: string | null
  error_message: string | null
  retry_count: number
}

export interface ExecutionRun {
  run_id: string
  flow_id: string
  flow_name?: string
  trigger_type: string
  status: RunStatus
  started_at: string | null
  ended_at: string | null
  rows_processed: number
  rows_failed: number
  rows_written: number
  steps: StepExecution[]
  error_message: string | null
  triggered_by: string
}

// ─── Canvas node types ────────────────────────────────────────────────
export type NodeFamily = 'trigger' | 'connector' | 'transform' | 'control' | 'utility'

export interface CanvasNodeData extends Record<string, unknown> {
  label: string
  stepType: string
  family: NodeFamily
  config: Record<string, unknown>
  status?: StepStatus
  rowsOut?: number
  error?: string
}

// ─── SSE Events ───────────────────────────────────────────────────────
export type FlowEventType =
  | 'run.started' | 'run.completed' | 'run.failed'
  | 'step.started' | 'step.completed' | 'step.failed' | 'step.retrying' | 'step.skipped'
  | 'log'

export interface FlowEvent {
  type: FlowEventType
  run_id: string
  flow_id: string
  step_id?: string
  timestamp: number
  payload: Record<string, unknown>
}
