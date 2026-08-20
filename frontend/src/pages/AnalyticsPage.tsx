import { useEffect, useState } from 'react'
import { PageHeading } from '../components/PageHeading'
import { apiGet, apiPost } from '../lib/apiClient'
import type {
  Decision,
  FraudAssessment,
  RiskLevel,
  TransactionListResponse,
  TransactionSummary,
} from '../lib/types'

// A "reasonable batch" for aggregate stats, not the whole table - same
// reasoning as the dashboard/investigations pages.
const BATCH_SIZE = 30

const RISK_LEVELS: RiskLevel[] = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']
const DECISIONS: Decision[] = ['ALLOW', 'STEP_UP', 'MANUAL_REVIEW', 'BLOCK']

type LoadStatus = 'loading-transactions' | 'assessing-risk' | 'ready' | 'error'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  )
}

function DistributionBars({
  title,
  counts,
  total,
}: {
  title: string
  counts: Record<string, number>
  total: number
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 text-sm font-medium text-slate-700">{title}</div>
      <div className="space-y-2">
        {Object.entries(counts).map(([label, count]) => {
          const pct = total === 0 ? 0 : (count / total) * 100
          return (
            <div key={label}>
              <div className="mb-1 flex justify-between text-xs text-slate-600">
                <span>{label}</span>
                <span>
                  {count} ({pct.toFixed(0)}%)
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-slate-700"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function AnalyticsPage() {
  const [status, setStatus] = useState<LoadStatus>('loading-transactions')
  const [error, setError] = useState<string | null>(null)
  const [assessments, setAssessments] = useState<FraudAssessment[]>([])
  const [assessedCount, setAssessedCount] = useState(0)

  async function load() {
    setStatus('loading-transactions')
    setError(null)
    setAssessments([])
    setAssessedCount(0)
    try {
      const list = await apiGet<TransactionListResponse>(`/transactions?limit=${BATCH_SIZE}`)
      const items: TransactionSummary[] = list.items

      if (items.length === 0) {
        setStatus('ready')
        return
      }

      setStatus('assessing-risk')
      // Sequential, not Promise.all - same reason as the dashboard: each
      // assessment call shares a limited DB connection pool.
      const results: FraudAssessment[] = []
      for (const txn of items) {
        const result = await apiPost<FraudAssessment>('/fraud/assess', {
          transaction_id: txn.id,
        })
        results.push(result)
        setAssessments([...results])
        setAssessedCount(results.length)
      }
      setStatus('ready')
    } catch {
      setError('Could not load analytics. Is the backend running?')
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const total = assessments.length
  const avgRiskScore =
    total === 0 ? 0 : assessments.reduce((sum, a) => sum + a.final_risk_score, 0) / total

  const riskLevelCounts = Object.fromEntries(
    RISK_LEVELS.map((level) => [level, assessments.filter((a) => a.risk_level === level).length]),
  )
  const decisionCounts = Object.fromEntries(
    DECISIONS.map((decision) => [
      decision,
      assessments.filter((a) => a.decision === decision).length,
    ]),
  )

  return (
    <div>
      <PageHeading
        title="Analytics"
        description={`Aggregate risk stats across the ${BATCH_SIZE} most recently assessed transactions.`}
      />

      {status === 'error' && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}{' '}
          <button onClick={load} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {(status === 'loading-transactions' || status === 'assessing-risk') && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          {status === 'loading-transactions'
            ? 'Loading transactions...'
            : `Assessing risk (${assessedCount}/${BATCH_SIZE})...`}
        </div>
      )}

      {status === 'ready' && total === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No transactions available to analyze.
        </div>
      )}

      {status === 'ready' && total > 0 && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard label="Transactions Assessed" value={total} />
            <StatCard label="Average Final Risk Score" value={avgRiskScore.toFixed(1)} />
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <DistributionBars title="Risk Level Distribution" counts={riskLevelCounts} total={total} />
            <DistributionBars title="Decision Distribution" counts={decisionCounts} total={total} />
          </div>
        </>
      )}
    </div>
  )
}
