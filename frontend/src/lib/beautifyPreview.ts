/** Client-side pretty-print for preview panes (fallback if API returns compact text). */

export function beautifyPreviewContent(content: string, format: string): string {
  const fmt = format.toLowerCase().replace(/^\./, '')
  if (!content.trim()) return content

  if (fmt === 'json') {
    try {
      return JSON.stringify(JSON.parse(content), null, 2) + '\n'
    } catch {
      return content
    }
  }

  if (fmt === 'xml') {
    return formatXmlReadable(content)
  }

  return content
}

function formatXmlReadable(xml: string): string {
  const trimmed = xml.trim()
  if (!trimmed) return xml
  try {
    const withBreaks = trimmed.replace(/>\s*</g, '>\n<')
    const lines = withBreaks.split('\n')
    let depth = 0
    const indent = '  '
    const out: string[] = []
    for (const line of lines) {
      const t = line.trim()
      if (!t) continue
      if (t.startsWith('</')) depth = Math.max(0, depth - 1)
      out.push(indent.repeat(depth) + t)
      if (
        t.startsWith('<') &&
        !t.startsWith('</') &&
        !t.endsWith('/>') &&
        !t.startsWith('<?') &&
        !t.includes('</')
      ) {
        depth += 1
      }
    }
    return out.join('\n') + '\n'
  } catch {
    return xml
  }
}
