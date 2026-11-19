import type { RiskLevel } from './types'
import { RISK_ORDER } from './riskOrder'

export function worseRisk(a: RiskLevel, b: RiskLevel): RiskLevel {
  if (a === 'unknown') return b
  if (b === 'unknown') return a
  return RISK_ORDER[a] >= RISK_ORDER[b] ? a : b
}
