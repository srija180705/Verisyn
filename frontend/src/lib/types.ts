// Shared types matching the backend's Pydantic response schemas
// (backend/app/schemas/transaction.py, backend/app/schemas/fraud.py).

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type Decision = 'ALLOW' | 'STEP_UP' | 'MANUAL_REVIEW' | 'BLOCK'

export interface TransactionSummary {
  id: string
  external_transaction_id: string
  amount: number
  currency: string
  transaction_type: string
  status: string
  occurred_at: string
  customer_external_id: string
  customer_name: string
  account_external_id: string
  account_type: string
}

export interface TransactionListResponse {
  total: number
  items: TransactionSummary[]
}

export interface FraudAssessment {
  transaction_id: string
  ml_score: number
  anomaly_score: number
  rule_score: number
  final_risk_score: number
  risk_level: RiskLevel
  decision: Decision
  triggered_rules: string[]
  features: Record<string, number | boolean>
}

// Advisory only - see backend/app/services/ai_explanation.py. Never
// affects ml_score/anomaly_score/rule_score/final_risk_score/risk_level/decision.
export interface AIExplanation {
  transaction_id: string
  available: boolean
  explanation: string
}

// Read-only snapshot of ml/rules.py + ml/risk.py, for the Rules tab.
export interface RuleConfig {
  name: string
  weight: number
  condition: string
}

export interface RulesConfig {
  rules: RuleConfig[]
  max_rule_score: number
  signal_weights: Record<string, number>
  risk_level_thresholds: Record<string, number>
  decision_by_risk_level: Record<string, string>
}
