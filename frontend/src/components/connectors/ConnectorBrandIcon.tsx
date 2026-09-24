import './ConnectorBrandIcon.css'

const STYLES: Record<string, { abbr: string; hue: string }> = {
  postgres: { abbr: 'PG', hue: '#336791' },
  salesforce: { abbr: 'SF', hue: '#00A1E0' },
  'aws-s3': { abbr: 'S3', hue: '#FF9900' },
  'rest-api': { abbr: 'API', hue: '#0070F2' },
  file: { abbr: 'FILE', hue: '#5C6BC0' },
  ftp: { abbr: 'FTP', hue: '#00897B' },
}

interface Props {
  connectorId: string
  size?: 'sm' | 'md' | 'lg'
}

export function ConnectorBrandIcon({ connectorId, size = 'md' }: Props) {
  const style = STYLES[connectorId] ?? {
    abbr: connectorId.slice(0, 3).toUpperCase(),
    hue: '#0070F2',
  }
  return (
    <span
      className={`conn-icon conn-icon--${size}`}
      style={{ '--conn-hue': style.hue } as React.CSSProperties}
    >
      {style.abbr}
    </span>
  )
}
