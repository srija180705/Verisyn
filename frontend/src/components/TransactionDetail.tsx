import { useEffect, useState } from 'react'
import { DemoBadge, isDemoTransaction } from './DemoBadge'
import { RiskBadge } from './RiskBadge'
import { apiGet, apiPost } from '../lib/apiClient'
import type { AIExplanation, Feedback, FeedbackLabel, FraudAssessment, TransactionSummary } from '../lib/types'

const FEEDBACK_LABELS: Record<FeedbackLabel, string> = {
  confirmed_fraud: 'Confirmed Fraud',
  confirmed_genuine: 'Confirmed Genuine',
}

interface TransactionDetailProps {
  transaction: TransactionSummary
  assessment: FraudAssessment
}

// Human-readable labels for the raw feature keys the backend returns.
// Keeps the investigation panel readable without a separate mapping file.
const FEATURE_LABELS: Record<string, string> = {
  amount_vs_customer_avg: 'Amount vs. customer average',
  transactions_last_10m: 'Transactions in last 10 min',
  transactions_last_1h: 'Transactions in last hour',
  is_new_device: 'New device for this customer',
  accounts_per_device: 'Accounts sharing this device (30d)',
  is_new_ip: 'New IP for this customer',
  accounts_per_ip: 'Accounts sharing this IP (30d)',
  time_since_last_transaction_seconds: 'Time since last transaction',
  failed_logins_last_10m: 'Failed logins in last 10 min',
  location_anomaly: 'Unusual location',
}

// "amount" is already shown as the headline transaction amount - no need
// to repeat it in the behavioral signals list.
const FEATURE_DISPLAY_ORDER = Object.keys(FEATURE_LABELS)

function formatFeatureValue(key: string, value: number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (key === 'time_since_last_transaction_seconds') {
    if (value < 0) return 'First transaction'
    const hours = value / 3600
    return hours >= 1 ? `${hours.toFixed(1)} hours ago` : `${Math.round(value / 60)} min ago`
  }
  if (key === 'amount_vs_customer_avg') return `${value.toFixed(2)}x`
  return String(value)
}

function ScoreCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold text-slate-900">{value.toFixed(1)}</div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1.5 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  )
}

type ExplanationStatus = 'idle' | 'loading' | 'done' | 'error'
type FeedbackStatus = 'loading' | 'ready' | 'submitting' | 'error'

export function TransactionDetail({ transaction, assessment }: TransactionDetailProps) {
  const [explanationStatus, setExplanationStatus] = useState<ExplanationStatus>('idle')
  const [explanation, setExplanation] = useState<AIExplanation | null>(null)

  const [feedbackStatus, setFeedbackStatus] = useState<FeedbackStatus>('loading')
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  // Switching to a different transaction should not keep showing the
  // previous one's explanation or feedback.
  useEffect(() => {
    setExplanationStatus('idle')
    setExplanation(null)

    setFeedbackStatus('loading')
    setFeedback(null)
    apiGet<Feedback>(`/feedback/${transaction.id}`)
      .then((result) => {
        setFeedback(result)
        setFeedbackStatus('ready')
      })
      .catch(() => {
        // No feedback submitted yet for this transaction - not an error.
        setFeedbackStatus('ready')
      })
  }, [transaction.id])

  async function handleGenerateExplanation() {
    setExplanationStatus('loading')
    try {
      const result = await apiPost<AIExplanation>('/fraud/explain', {
        transaction_id: transaction.id,
      })
      setExplanation(result)
      setExplanationStatus('done')
    } catch {
      setExplanationStatus('error')
    }
  }

  async function handleSubmitFeedback(label: FeedbackLabel) {
    setFeedbackStatus('submitting')
    try {
      const result = await apiPost<Feedback>('/feedback', {
        transaction_id: transaction.id,
        label,
      })
      setFeedback(result)
      setFeedbackStatus('ready')
    } catch {
      setFeedbackStatus('error')
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
            {transaction.external_transaction_id}
            {isDemoTransaction(transaction.external_transaction_id) && <DemoBadge />}
          </h2>
          <p className="text-sm text-slate-500">
            {transaction.amount.toFixed(2)} {transaction.currency} &middot;{' '}
            {transaction.transaction_type}
          </p>
        </div>
        <RiskBadge level={assessment.risk_level} />
      </div>

      <div className="mb-4">
        <div className="mb-1 text-sm font-medium text-slate-700">Transaction</div>
        <InfoRow label="Status" value={transaction.status} />
        <InfoRow
          label="Timestamp"
          value={new Date(transaction.occurred_at).toLocaleString()}
        />
        <InfoRow
          label="Customer"
          value={`${transaction.customer_name} (${transaction.customer_external_id})`}
        />
        <InfoRow
          label="Account"
          value={`${transaction.account_type} (${transaction.account_external_id})`}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ScoreCard label="ML Score" value={assessment.ml_score} />
        <ScoreCard label="Anomaly Score" value={assessment.anomaly_score} />
        <ScoreCard label="Rule Score" value={assessment.rule_score} />
        <ScoreCard label="Final Risk Score" value={assessment.final_risk_score} />
      </div>

      <div className="mt-4 flex items-center gap-2">
        <span className="text-sm text-slate-500">Decision:</span>
        <span className="rounded-md bg-slate-900 px-2.5 py-0.5 text-xs font-medium text-white">
          {assessment.decision}
        </span>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <div className="mb-2 text-sm font-medium text-slate-700">Reviewer Feedback</div>
        {feedbackStatus === 'error' && (
          <p className="mb-2 text-sm text-red-600">Could not submit feedback. Please try again.</p>
        )}
        {feedback && (
          <p className="mb-2 text-sm text-slate-600">
            Marked as <span className="font-medium">{FEEDBACK_LABELS[feedback.label]}</span> on{' '}
            {new Date(feedback.reviewed_at).toLocaleString()}.
          </p>
        )}
        <div className="flex gap-2">
          <button
            onClick={() => handleSubmitFeedback('confirmed_fraud')}
            disabled={feedbackStatus === 'submitting' || feedbackStatus === 'loading'}
            className={`rounded-md border px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${
              feedback?.label === 'confirmed_fraud'
                ? 'border-red-600 bg-red-600 text-white'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50'
            }`}
          >
            Confirm Fraud
          </button>
          <button
            onClick={() => handleSubmitFeedback('confirmed_genuine')}
            disabled={feedbackStatus === 'submitting' || feedbackStatus === 'loading'}
            className={`rounded-md border px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${
              feedback?.label === 'confirmed_genuine'
                ? 'border-green-600 bg-green-600 text-white'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50'
            }`}
          >
            Confirm Genuine
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Advisory feedback for reviewer records - does not change the score or decision above.
        </p>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-sm text-slate-500">Triggered Rules</div>
        {assessment.triggered_rules.length === 0 ? (
          <p className="text-sm text-slate-400">None</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {assessment.triggered_rules.map((rule) => (
              <span
                key={rule}
                className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
              >
                {rule}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4">
        <div className="mb-1 text-sm font-medium text-slate-700">Behavioral Signals</div>
        {FEATURE_DISPLAY_ORDER.filter((key) => key in assessment.features).map((key) => (
          <InfoRow
            key={key}
            label={FEATURE_LABELS[key]}
            value={formatFeatureValue(key, assessment.features[key])}
          />
        ))}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-medium text-slate-700">AI Explanation</div>
          <button
            onClick={handleGenerateExplanation}
            disabled={explanationStatus === 'loading'}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {explanationStatus === 'loading' ? 'Generating...' : 'Generate AI Explanation'}
          </button>
        </div>

        {explanationStatus === 'error' && (
          <p className="text-sm text-red-600">
            Could not generate an explanation. Please try again.
          </p>
        )}

        {explanationStatus === 'done' && explanation && (
          <p
            className={`text-sm ${explanation.available ? 'text-slate-700' : 'text-slate-400 italic'}`}
          >
            {explanation.explanation}
          </p>
        )}

        {explanationStatus === 'idle' && (
          <p className="text-sm text-slate-400">
            Advisory only - does not affect the score or decision above.
          </p>
        )}
      </div>
    </div>
  )
}
