/** Connector setup wizard for source/target steps in the flow designer. */
import type { CanvasNodeData } from '@/types'
import { ConnectorWizard } from './ConnectorWizard'
import './ConnectorNodeConfig.css'

interface Props {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
  mode: 'source' | 'target'
}

export function ConnectorNodeConfig({ data, onUpdate, mode }: Props) {
  return <ConnectorWizard data={data} onUpdate={onUpdate} mode={mode} />
}
