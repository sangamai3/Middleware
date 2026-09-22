import type { NodeTypes } from '@xyflow/react'
import { BaseNode } from './BaseNode'

export const nodeTypes: NodeTypes = {
  // Triggers
  scheduler: BaseNode,
  webhook_trigger: BaseNode,
  streaming_trigger: BaseNode,
  event_trigger: BaseNode,
  // Data
  connector_read: BaseNode,
  connector_write: BaseNode,
  // Transforms
  transform_format: BaseNode,
  transform_map: BaseNode,
  transform_filter: BaseNode,
  transform_sql: BaseNode,
  transform_script: BaseNode,
  // Control
  router: BaseNode,
  merge: BaseNode,
  iterator: BaseNode,
  sub_flow: BaseNode,
  // Utility
  set_variable: BaseNode,
  lookup_table: BaseNode,
  approval: BaseNode,
  notification: BaseNode,
  logger: BaseNode,
  sync_endpoint: BaseNode,
  // Exception
  global_exception: BaseNode,
  component_exception: BaseNode,
} as NodeTypes
