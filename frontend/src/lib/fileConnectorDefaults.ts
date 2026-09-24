export const FILE_SOURCE_OBJECT_DEFAULT = '*.csv'
export const FILE_TARGET_OBJECT_DEFAULT = 'output.csv'

export function fileObjectDefault(
  mode: 'source' | 'target',
  writePerSource?: boolean,
): string | null {
  if (mode === 'source') return FILE_SOURCE_OBJECT_DEFAULT
  if (writePerSource) return null
  return FILE_TARGET_OBJECT_DEFAULT
}

/** Resolved object/pattern for file connector steps (applies defaults when blank). */
export function resolveFileObject(
  cfg: Record<string, unknown>,
  mode: 'source' | 'target',
): string {
  const trimmed = String(cfg.object ?? '').trim()
  if (trimmed) return trimmed
  const writePerSource =
    cfg.write_per_source === true || cfg.write_per_source === 'true'
  return fileObjectDefault(mode, writePerSource) ?? ''
}
