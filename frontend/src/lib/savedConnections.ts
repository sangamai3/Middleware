/** Client-side saved connections until platform connection store is wired in flows. */

export interface SavedConnection {
  id: string
  name: string
  connector_id: string
  config: Record<string, string | boolean | number>
  updated_at: string
}

const STORAGE_KEY = 'sangam_mw.saved_connections.v1'

function readAll(): SavedConnection[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as SavedConnection[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(items: SavedConnection[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export function listSavedConnections(connectorId?: string): SavedConnection[] {
  const all = readAll()
  if (!connectorId) return all
  return all.filter((c) => c.connector_id === connectorId)
}

export function getSavedConnection(id: string): SavedConnection | undefined {
  return readAll().find((c) => c.id === id)
}

export function upsertSavedConnection(
  connectorId: string,
  name: string,
  config: Record<string, string | boolean | number>,
  existingId?: string,
): SavedConnection {
  const all = readAll()
  const now = new Date().toISOString()
  const entry: SavedConnection = {
    id: existingId || `conn_${Date.now()}`,
    name: name.trim() || `${connectorId} connection`,
    connector_id: connectorId,
    config,
    updated_at: now,
  }
  const idx = all.findIndex((c) => c.id === entry.id)
  if (idx >= 0) all[idx] = entry
  else all.unshift(entry)
  writeAll(all.slice(0, 50))
  return entry
}

export function deleteSavedConnection(id: string) {
  writeAll(readAll().filter((c) => c.id !== id))
}
