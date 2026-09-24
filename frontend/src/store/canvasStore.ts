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
  duplicateNode: (id: string) => void
  autoLayout: () => void

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

  duplicateNode: (id) => {
    const src = get().nodes.find((n) => n.id === id)
    if (!src) return
    const newId = `node_${Date.now()}_dup`
    const copy: CanvasNode = {
      ...src,
      id: newId,
      position: { x: src.position.x + 40, y: src.position.y + 60 },
      data: { ...src.data, config: { ...(src.data.config as Record<string, unknown>) } },
    }
    set({ nodes: [...get().nodes, copy], selectedNodeId: newId })
    markFlowDirty()
  },

  autoLayout: () => {
    const { nodes, edges } = get()
    if (nodes.length === 0) return

    // Build incoming-degree and children maps
    const inDeg = new Map<string, number>()
    const children = new Map<string, string[]>()
    nodes.forEach(n => { inDeg.set(n.id, 0); children.set(n.id, []) })
    edges.forEach(e => {
      inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1)
      children.get(e.source)?.push(e.target)
    })

    // BFS layer assignment (Kahn-style)
    const layer = new Map<string, number>()
    const queue: string[] = []
    nodes.forEach(n => { if ((inDeg.get(n.id) ?? 0) === 0) { queue.push(n.id); layer.set(n.id, 0) } })

    while (queue.length > 0) {
      const id = queue.shift()!
      const l = layer.get(id) ?? 0
      for (const child of children.get(id) ?? []) {
        layer.set(child, Math.max(layer.get(child) ?? 0, l + 1))
        queue.push(child)
      }
    }
    // Disconnected nodes get their own layer
    let maxLayer = Math.max(0, ...[...layer.values()])
    nodes.forEach(n => { if (!layer.has(n.id)) { layer.set(n.id, ++maxLayer) } })

    // Group by layer
    const byLayer = new Map<number, string[]>()
    layer.forEach((l, id) => {
      if (!byLayer.has(l)) byLayer.set(l, [])
      byLayer.get(l)!.push(id)
    })

    const COL_W = 240, ROW_H = 115, START_X = 80
    const posMap = new Map<string, { x: number; y: number }>()
    byLayer.forEach((ids, l) => {
      const total = ids.length * ROW_H
      ids.forEach((id, i) => {
        posMap.set(id, { x: START_X + l * COL_W, y: 60 + i * ROW_H - (total - ROW_H) / 2 })
      })
    })

    set({ nodes: nodes.map(n => ({ ...n, position: posMap.get(n.id) ?? n.position })) })
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
