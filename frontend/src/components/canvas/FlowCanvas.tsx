import { useCallback, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  ConnectionLineType,
  ConnectionMode,
  useReactFlow,
  useViewport,
} from '@xyflow/react'
import type { Connection, Edge, Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCanvasStore } from '@/store/canvasStore'
import { nodeTypes } from '../nodes/nodeTypes'
import type { CanvasNodeData, NodeFamily } from '@/types'
import type { CanvasNode } from '../nodes/BaseNode'
import './FlowCanvas.css'

function ZoomIndicator() {
  const { zoom } = useViewport()
  return (
    <div className="flow-canvas__zoom-indicator" title="Current zoom level">
      {Math.round(zoom * 100)}%
    </div>
  )
}

let nodeCounter = 1

function makeNodeId() {
  return `node_${Date.now()}_${nodeCounter++}`
}

const FAMILY_FOR_TYPE: Record<string, NodeFamily> = {
  scheduler: 'trigger', webhook_trigger: 'trigger', streaming_trigger: 'trigger', event_trigger: 'trigger',
  connector_read: 'connector', connector_write: 'connector',
  transform_format: 'transform',
  transform_map: 'transform', transform_filter: 'transform', transform_sql: 'transform', transform_script: 'transform',
  router: 'control', merge: 'control', iterator: 'control', sub_flow: 'control',
  set_variable: 'utility', logger: 'utility', approval: 'utility', notification: 'utility',
  sync_endpoint: 'utility', lookup_table: 'utility',
  global_exception: 'utility', component_exception: 'utility',
}

type ContextMenu = { x: number; y: number; nodeId: string; nodeLabel: string }

export function FlowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, addNode, selectNode, deleteNode, duplicateNode } =
    useCanvasStore()
  const { screenToFlowPosition } = useReactFlow()
  const dropRef = useRef<HTMLDivElement>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null)

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const raw = e.dataTransfer.getData('application/sangam-node')
      if (!raw) return
      const item = JSON.parse(raw) as { stepType: string; label: string; family: NodeFamily }
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      const id = makeNodeId()
      const node: CanvasNode = {
        id,
        type: item.stepType,
        position,
        data: {
          label: item.label,
          stepType: item.stepType,
          family: item.family || FAMILY_FOR_TYPE[item.stepType] || 'utility',
          config: {},
        },
      }
      addNode(node)
      selectNode(id)
    },
    [screenToFlowPosition, addNode, selectNode],
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => selectNode(node.id),
    [selectNode],
  )

  const onPaneClick = useCallback(() => {
    selectNode(null)
    setContextMenu(null)
  }, [selectNode])

  const onNodeContextMenu = useCallback(
    (e: React.MouseEvent, node: Node) => {
      e.preventDefault()
      selectNode(node.id)
      const label = String((node.data as CanvasNodeData).label ?? node.id)
      setContextMenu({ x: e.clientX, y: e.clientY, nodeId: node.id, nodeLabel: label })
    },
    [selectNode],
  )

  const isValidConnection = useCallback(
    (edge: Connection | Edge) => edge.source !== edge.target,
    [],
  )

  return (
    <div ref={dropRef} className="flow-canvas" onDrop={onDrop} onDragOver={onDragOver}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onNodeContextMenu={onNodeContextMenu}
        isValidConnection={isValidConnection}
        connectionMode={ConnectionMode.Loose}
        connectionRadius={48}
        nodesConnectable
        edgesReconnectable
        connectOnClick={false}
        connectionLineType={ConnectionLineType.SmoothStep}
        connectionLineStyle={{
          stroke: 'var(--accent)',
          strokeWidth: 2.5,
          strokeDasharray: '6 4',
        }}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: { strokeWidth: 2, stroke: 'color-mix(in srgb, var(--accent) 85%, var(--text-muted))' },
          interactionWidth: 24,
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode={null}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border-subtle)" />
        <Controls showInteractive={false} />
        <ZoomIndicator />
        <MiniMap
          nodeColor={(n) => {
            const family = (n.data as CanvasNodeData).family
            const map: Record<string, string> = {
              trigger: 'var(--node-trigger)', connector: 'var(--node-connector)',
              transform: 'var(--node-transform)', control: 'var(--node-control)', utility: 'var(--node-utility)',
            }
            return map[family] || 'var(--border)'
          }}
          maskColor="rgba(0,0,0,0.4)"
        />
      </ReactFlow>

      {nodes.length === 0 && (
        <div className="flow-canvas__empty">
          <p>Drag a node from the palette to start building your flow</p>
        </div>
      )}

      {contextMenu && (
        <div
          className="canvas-context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onMouseLeave={() => setContextMenu(null)}
        >
          <div className="canvas-context-menu__label">{contextMenu.nodeLabel}</div>
          <button
            type="button"
            className="canvas-context-menu__item"
            onClick={() => { duplicateNode(contextMenu.nodeId); setContextMenu(null) }}
          >
            <span>⧉</span> Duplicate  <kbd>⌘D</kbd>
          </button>
          <button
            type="button"
            className="canvas-context-menu__item canvas-context-menu__item--danger"
            onClick={() => { deleteNode(contextMenu.nodeId); setContextMenu(null) }}
          >
            <span>✕</span> Delete  <kbd>Del</kbd>
          </button>
        </div>
      )}
    </div>
  )
}
