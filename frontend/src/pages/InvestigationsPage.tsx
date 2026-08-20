import { useEffect, useState } from 'react'
import { PageHeading } from '../components/PageHeading'
import { RiskBadge } from '../components/RiskBadge'
import { TransactionDetail } from '../components/TransactionDetail'
import { apiGet, apiPost } from '../lib/apiClient'
import type { FraudAssessment, TransactionListResponse, TransactionSummary } from '../lib/types'

// A "reasonable batch" per the task, not the whole table - assessed
// sequentially below (same reasoning as the dashboard: firing these
// concurrently exhausts the DB connection pool).
const BATCH_SIZE = 25

type LoadStatus = 'loading-transactions' | 'assessing-risk' | 'ready' | 'error'

function needsAttention(a: FraudAssessment): boolean {
  return a.risk_level === 'HIGH' || a.risk_level === 'CRITICAL' || a.decision !== 'ALLOW'
}

export function InvestigationsPage() {
  const [status, setStatus] = useState<LoadStatus>('loading-transactions')
  const [error, setError] = useState<string | null>(null)
  const [transactions, setTransactions] = useState<TransactionSummary[]>([])
  const [assessments, setAssessments] = useState<Record<string, FraudAssessment>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)

  async function load() {
    setStatus('loading-transactions')
    setError(null)
    setSelectedId(null)
    try {
      const list = await apiGet<TransactionListResponse>(`/transactions?limit=${BATCH_SIZE}`)
      setTransactions(list.items)

      if (list.items.length === 0) {
        setStatus('ready')
        return
      }

      setStatus('assessing-risk')
      // Sequential, not Promise.all - same reason as the dashboard: each
      // assessment call shares a limited DB connection pool.
      const byId: Record<string, FraudAssessment> = {}
      for (const txn of list.items) {
        const result = await apiPost<FraudAssessment>('/fraud/assess', {
          transaction_id: txn.id,
        })
        byId[result.transaction_id] = result
        setAssessments({ ...byId })
      }
      setStatus('ready')
    } catch {
      setError('Could not load investigations. Is the backend running?')
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const flagged = transactions.filter((txn) => {
    const a = assessments[txn.id]
    return a && needsAttention(a)
  })

  const selectedTransaction = transactions.find((t) => t.id === selectedId) ?? null
  const selectedAssessment = selectedId ? assessments[selectedId] : undefined

  return (
    <div>
      <PageHeading
        title="Investigations"
        description={`Transactions needing attention (HIGH/CRITICAL risk or a non-ALLOW decision) among the ${BATCH_SIZE} most recent transactions.`}
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
            : `Assessing risk (this checks ${BATCH_SIZE} recent transactions)...`}
        </div>
      )}

      {status === 'ready' && flagged.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No high-risk or non-ALLOW transactions were found in the recent transactions assessed.
        </div>
      )}

      {status === 'ready' && flagged.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Transaction</th>
                  <th className="px-4 py-2">Customer</th>
                  <th className="px-4 py-2">Amount</th>
                  <th className="px-4 py-2">Risk</th>
                  <th className="px-4 py-2">Level</th>
                  <th className="px-4 py-2">Decision</th>
                </tr>
              </thead>
              <tbody>
                {flagged.map((txn) => {
                  const assessment = assessments[txn.id]
                  return (
                    <tr
                      key={txn.id}
                      onClick={() => setSelectedId(txn.id)}
                      className={`cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 ${
                        txn.id === selectedId ? 'bg-slate-50' : ''
                      }`}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-slate-700">
                        {txn.external_transaction_id}
                      </td>
                      <td className="px-4 py-2 text-slate-700">{txn.customer_name}</td>
                      <td className="px-4 py-2 text-slate-700">
                        {txn.amount.toFixed(2)} {txn.currency}
                      </td>
                      <td className="px-4 py-2 text-slate-700">
                        {assessment.final_risk_score.toFixed(1)}
                      </td>
                      <td className="px-4 py-2">
                        <RiskBadge level={assessment.risk_level} />
                      </td>
                      <td className="px-4 py-2 text-slate-700">{assessment.decision}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {selectedTransaction && selectedAssessment && (
            <TransactionDetail transaction={selectedTransaction} assessment={selectedAssessment} />
          )}
        </div>
      )}
    </div>
  )
}
