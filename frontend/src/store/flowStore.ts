import { create } from 'zustand'
import type { FlowDefinition } from '@/types'

interface FlowStore {
  currentFlow: FlowDefinition | null
  isDirty: boolean
  setFlow: (flow: FlowDefinition) => void
  updateFlow: (patch: Partial<FlowDefinition>) => void
  markClean: () => void
}

export const useFlowStore = create<FlowStore>((set) => ({
  currentFlow: null,
  isDirty: false,
  setFlow: (flow) => set({ currentFlow: flow, isDirty: false }),
  updateFlow: (patch) =>
    set((s) => ({
      currentFlow: s.currentFlow ? { ...s.currentFlow, ...patch } : null,
      isDirty: true,
    })),
  markClean: () => set({ isDirty: false }),
}))
