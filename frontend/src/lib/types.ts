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
