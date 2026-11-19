import type { RiskLevel } from './types'

export const RISK_ORDER: Record<RiskLevel, number> = {
  low: 1,
  moderate: 2,
  high: 3,
  severe: 4,
  no_travel: 5,
  unknown: 0,
}
