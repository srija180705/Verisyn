import type { RiskLevel } from '../lib/types'

const RISK_LEVEL_STYLES: Record<RiskLevel, string> = {
  LOW: 'bg-green-100 text-green-800',
  MODERATE: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${RISK_LEVEL_STYLES[level]}`}
    >
      {level}
    </span>
  )
}
