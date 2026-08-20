import { useEffect, useState } from 'react'
import { DemoBadge, isDemoTransaction } from '../components/DemoBadge'
import { PageHeading } from '../components/PageHeading'
import { RiskBadge } from '../components/RiskBadge'
import { TransactionDetail } from '../components/TransactionDetail'
import { apiGet, apiPost } from '../lib/apiClient'
import type { FraudAssessment, TransactionListResponse, TransactionSummary } from '../lib/types'

const RECENT_LIMIT = 10

type LoadStatus = 'loading-transactions' | 'assessing-risk' | 'ready' | 'error'

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  )
}

export function DashboardPage() {
  const [status, setStatus] = useState<LoadStatus>('loading-transactions')
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [transactions, setTransactions] = useState<TransactionSummary[]>([])
  const [assessments, setAssessments] = useState<Record<string, FraudAssessment>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)

  async function load() {
    setStatus('loading-transactions')
    setError(null)
    try {
      const list = await apiGet<TransactionListResponse>(
        `/transactions?limit=${RECENT_LIMIT}`,
      )
      setTotal(list.total)
      setTransactions(list.items)

      if (list.items.length === 0) {
        setStatus('ready')
        return
      }

      setStatus('assessing-risk')
      // Sequential, not Promise.all: each assessment replays the full
      // transaction history server-side, so firing them all at once
      // exhausts the DB connection pool. One at a time is slower but
      // reliable, and the table fills in progressively as each arrives.
      const byId: Record<string, FraudAssessment> = {}
      for (const txn of list.items) {
        const result = await apiPost<FraudAssessment>('/fraud/assess', {
          transaction_id: txn.id,
        })
        byId[result.transaction_id] = result
        setAssessments({ ...byId })
      }
      setSelectedId(list.items[0].id)
      setStatus('ready')
    } catch {
      setError('Could not load the dashboard. Is the backend running?')
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const highRiskCount = Object.values(assessments).filter(
    (a) => a.risk_level === 'HIGH' || a.risk_level === 'CRITICAL',
  ).length
  const blockedCount = Object.values(assessments).filter((a) => a.decision === 'BLOCK').length

  const selectedTransaction = transactions.find((t) => t.id === selectedId) ?? null
  const selectedAssessment = selectedId ? assessments[selectedId] : undefined

  return (
    <div>
      <PageHeading
        title="Dashboard"
        description="Fraud operations overview for the most recent transactions."
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
            : 'Assessing risk for recent transactions...'}
        </div>
      )}

      {status === 'ready' && transactions.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No transactions found.
        </div>
      )}

      {status === 'ready' && transactions.length > 0 && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Total Transactions" value={total} />
            <StatCard label="High-Risk (recent)" value={highRiskCount} />
            <StatCard label="Critical / Blocked (recent)" value={blockedCount} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Transaction</th>
                    <th className="px-4 py-2">Amount</th>
                    <th className="px-4 py-2">Risk Score</th>
                    <th className="px-4 py-2">Level</th>
                    <th className="px-4 py-2">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => {
                    const assessment = assessments[txn.id]
                    const isSelected = txn.id === selectedId
                    return (
                      <tr
                        key={txn.id}
                        onClick={() => setSelectedId(txn.id)}
                        className={`cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 ${
                          isSelected ? 'bg-slate-50' : ''
                        }`}
                      >
                        <td className="px-4 py-2 font-mono text-xs text-slate-700">
                          <span className="inline-flex items-center gap-1.5">
                            {txn.external_transaction_id}
                            {isDemoTransaction(txn.external_transaction_id) && <DemoBadge />}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-700">
                          {txn.amount.toFixed(2)} {txn.currency}
                        </td>
                        <td className="px-4 py-2 text-slate-700">
                          {assessment ? assessment.final_risk_score.toFixed(1) : '-'}
                        </td>
                        <td className="px-4 py-2">
                          {assessment ? <RiskBadge level={assessment.risk_level} /> : '-'}
                        </td>
                        <td className="px-4 py-2 text-slate-700">
                          {assessment ? assessment.decision : '-'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {selectedTransaction && selectedAssessment && (
              <TransactionDetail
                transaction={selectedTransaction}
                assessment={selectedAssessment}
              />
            )}
          </div>
        </>
      )}
    </div>
  )
}
