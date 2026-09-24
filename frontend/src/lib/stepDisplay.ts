import type { StepExecution } from '@/types'

const ROLE: Record<string, string> = {
  connector_read: 'Source',
  connector_write: 'Target',
  transform_format: 'Format Convert',
  transform_map: 'Map Fields',
  transform_filter: 'Filter',
  transform_sql: 'SQL',
  transform_script: 'Script',
}

const CONNECTOR: Record<string, string> = {
  file: 'File',
  postgres: 'PostgreSQL',
  'aws-s3': 'Amazon S3',
  salesforce: 'Salesforce',
  'rest-api': 'REST API',
}

/** Primary line for run timeline (falls back for older runs without step_label). */
export function stepTimelineTitle(step: StepExecution): string {
  if (step.step_label?.trim()) return step.step_label.trim()
  const role = ROLE[step.step_type] ?? step.step_type.replace(/_/g, ' ')
  const parts = [role]
  if (step.connector_id) {
    parts.push(CONNECTOR[step.connector_id] ?? step.connector_id)
  }
  return parts.join(' · ')
}
