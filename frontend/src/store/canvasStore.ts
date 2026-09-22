import { create } from 'zustand'
import { addEdge, applyNodeChanges, applyEdgeChanges } from '@xyflow/react'
import type { Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import type { CanvasNodeData, FlowEvent, StepStatus } from '@/types'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import { useFlowStore } from '@/store/flowStore'

const markFlowDirty = () => useFlowStore.getState().updateFlow({})

interface CanvasStore {
  nodes: CanvasNode[]
  edges: Edge[]
  selectedNodeId: string | null
  runId: string | null
  isRunning: boolean

  setNodes: (nodes: CanvasNode[]) => void
  setEdges: (edges: Edge[]) => void
  onNodesChange: (changes: NodeChange<CanvasNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (node: CanvasNode) => void
  updateNodeData: (id: string, data: Partial<CanvasNodeData>) => void
  deleteNode: (id: string) => void

  selectNode: (id: string | null) => void

  setRunId: (id: string | null) => void
  setRunning: (running: boolean) => void
  applyFlowEvent: (event: FlowEvent) => void
  resetRunState: () => void
}

export const useCanvasStore = create<CanvasStore>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  runId: null,
  isRunning: false,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),

  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (connection) =>
    set({ edges: addEdge({ ...connection, animated: false }, get().edges) }),

  addNode: (node) => {
    set({ nodes: [...get().nodes, node] })
    markFlowDirty()
  },

  updateNodeData: (id, data) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n,
      ),
    })
    markFlowDirty()
  },

  deleteNode: (id) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: get().selectedNodeId === id ? null : get().selectedNodeId,
    })
    markFlowDirty()
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  setRunId: (id) => set({ runId: id }),
  setRunning: (running) => set({ isRunning: running }),

  applyFlowEvent: (event) => {
    const { type, step_id, payload } = event
    if (!step_id) return

    const statusMap: Record<string, StepStatus> = {
      'step.started': 'running',
      'step.completed': 'success',
      'step.failed': 'failed',
      'step.retrying': 'retrying',
      'step.skipped': 'skipped',
    }
    const status = statusMap[type]
    if (!status) return

    set({
      nodes: get().nodes.map((n) => {
        if (n.data.stepType && n.id === step_id) {
          return {
            ...n,
            data: {
              ...n.data,
              status,
              rowsOut: typeof payload.rows_out === 'number' ? payload.rows_out : n.data.rowsOut,
              error: typeof payload.error === 'string' ? payload.error : undefined,
            },
          }
        }
        return n
      }),
    })
  },

  resetRunState: () =>
    set({
      nodes: get().nodes.map((n) => ({
        ...n,
        data: { ...n.data, status: undefined, rowsOut: undefined, error: undefined },
      })),
      runId: null,
      isRunning: false,
    }),
}))
