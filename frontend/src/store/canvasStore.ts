import { create } from 'zustand'
import { addEdge, applyNodeChanges, applyEdgeChanges } from '@xyflow/react'
import type { Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import type { CanvasNodeData, ExecutionRun, FlowEvent, StepStatus } from '@/types'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import { useFlowStore } from '@/store/flowStore'

const markFlowDirty = () => useFlowStore.getState().updateFlow({})

interface CanvasStore {
  nodes: CanvasNode[]
  edges: Edge[]
  selectedNodeId: string | null
  runId: string | null
  isRunning: boolean
  runResult: ExecutionRun | null
  runPanelOpen: boolean

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
  setRunResult: (run: ExecutionRun | null) => void
  setRunPanelOpen: (open: boolean) => void
  applyFlowEvent: (event: FlowEvent) => void
  resetRunState: () => void
}

export const useCanvasStore = create<CanvasStore>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  runId: null,
  isRunning: false,
  runResult: null,
  runPanelOpen: false,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    // Only explicit "Remove step" in the config panel may delete nodes (not Backspace/Delete).
    const safe = changes.filter((c) => c.type !== 'remove')
    if (safe.length === 0) return
    set({ nodes: applyNodeChanges(safe, get().nodes) })
  },

  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (connection) => {
    const normalized: Connection = {
      ...connection,
      sourceHandle: connection.sourceHandle ?? 'out',
      targetHandle: connection.targetHandle ?? 'in',
    }
    set({
      edges: addEdge(
        {
          ...normalized,
          type: 'smoothstep',
          animated: false,
          style: { strokeWidth: 2, stroke: 'color-mix(in srgb, var(--accent) 85%, var(--text-muted))' },
          interactionWidth: 24,
        },
        get().edges,
      ),
    })
    markFlowDirty()
  },

  addNode: (node) => {
    set({ nodes: [...get().nodes, node] })
    markFlowDirty()
  },

  updateNodeData: (id, data) => {
    set({
      nodes: get().nodes.map((n) => {
        if (n.id !== id) return n
        const merged: CanvasNodeData = { ...n.data, ...data }
        if (data.config !== undefined) {
          const prev = (n.data.config ?? {}) as Record<string, unknown>
          const next = data.config as Record<string, unknown>
          const prevConn = (prev.conn ?? {}) as Record<string, unknown>
          const nextConn = next.conn as Record<string, unknown> | undefined
          merged.config = {
            ...prev,
            ...next,
            ...(nextConn ? { conn: { ...prevConn, ...nextConn } } : {}),
          }
        }
        return { ...n, data: merged }
      }),
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
  setRunResult: (run) => set({ runResult: run }),
  setRunPanelOpen: (open) => set({ runPanelOpen: open }),

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
