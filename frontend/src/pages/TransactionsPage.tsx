import { useEffect, useState } from 'react'
import { PageHeading } from '../components/PageHeading'
import { TransactionDetail } from '../components/TransactionDetail'
import { onRowKeyDown } from '../lib/a11y'
import { apiGet, apiPost } from '../lib/apiClient'
import type { FraudAssessment, TransactionListResponse, TransactionSummary } from '../lib/types'

const PAGE_SIZE = 20
const STATUS_OPTIONS = ['pending', 'completed', 'failed', 'cancelled', 'reversed']

type ListStatus = 'loading' | 'ready' | 'error'
type AssessStatus = 'idle' | 'loading' | 'ready' | 'error'

export function TransactionsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)

  const [listStatus, setListStatus] = useState<ListStatus>('loading')
  const [total, setTotal] = useState(0)
  const [transactions, setTransactions] = useState<TransactionSummary[]>([])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [assessStatus, setAssessStatus] = useState<AssessStatus>('idle')
  const [assessment, setAssessment] = useState<FraudAssessment | null>(null)

  // Debounce search so we don't fire a request on every keystroke.
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timeout)
  }, [search])

  // Any filter change goes back to page 1.
  useEffect(() => {
    setOffset(0)
  }, [debouncedSearch, status])

  async function loadList() {
    setListStatus('loading')
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      })
      if (debouncedSearch) params.set('search', debouncedSearch)
      if (status) params.set('status', status)

      const result = await apiGet<TransactionListResponse>(`/transactions?${params}`)
      setTotal(result.total)
      setTransactions(result.items)
      setListStatus('ready')
    } catch {
      setListStatus('error')
    }
  }

  useEffect(() => {
    loadList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch, status, offset])

  async function selectTransaction(txn: TransactionSummary) {
    setSelectedId(txn.id)
    setAssessStatus('loading')
    setAssessment(null)
    try {
      const result = await apiPost<FraudAssessment>('/fraud/assess', {
        transaction_id: txn.id,
      })
      setAssessment(result)
      setAssessStatus('ready')
    } catch {
      setAssessStatus('error')
    }
  }

  const selectedTransaction = transactions.find((t) => t.id === selectedId) ?? null
  const rangeStart = total === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(offset + PAGE_SIZE, total)

  return (
    <div>
      <PageHeading
        title="Transactions"
        description="Browse and search all transactions. Select one to run a fraud assessment."
      />

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="min-w-[280px] flex-1">
          <label htmlFor="transaction-search" className="sr-only">
            Search by transaction ID, customer name, or customer ID
          </label>
          <input
            id="transaction-search"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by transaction ID, customer name, or customer ID..."
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label htmlFor="transaction-status" className="sr-only">
            Filter by status
          </label>
          <select
            id="transaction-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {listStatus === 'error' && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Could not load transactions.{' '}
          <button onClick={loadList} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {listStatus === 'loading' && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          Loading transactions...
        </div>
      )}

      {listStatus === 'ready' && transactions.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No transactions match your filters.
        </div>
      )}

      {listStatus === 'ready' && transactions.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <div className="rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Transaction</th>
                    <th className="px-4 py-2">Amount</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Customer</th>
                    <th className="px-4 py-2">Occurred</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => (
                    <tr
                      key={txn.id}
                      onClick={() => selectTransaction(txn)}
                      onKeyDown={onRowKeyDown(() => selectTransaction(txn))}
                      tabIndex={0}
                      role="button"
                      aria-label={`View details for transaction ${txn.external_transaction_id}`}
                      className={`cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 focus:outline focus:outline-2 focus:outline-offset-[-2px] focus:outline-slate-900 ${
                        txn.id === selectedId ? 'bg-slate-50' : ''
                      }`}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-slate-700">
                        {txn.external_transaction_id}
                      </td>
                      <td className="px-4 py-2 text-slate-700">
                        {txn.amount.toFixed(2)} {txn.currency}
                      </td>
                      <td className="px-4 py-2 text-slate-700">{txn.status}</td>
                      <td className="px-4 py-2 text-slate-700">{txn.customer_name}</td>
                      <td className="px-4 py-2 text-slate-500">
                        {new Date(txn.occurred_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
              <span>
                {rangeStart}-{rangeEnd} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= total}
                  className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          <div>
            {assessStatus === 'idle' && (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
                Select a transaction to view its fraud assessment.
              </div>
            )}
            {assessStatus === 'loading' && (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
                Assessing risk...
              </div>
            )}
            {assessStatus === 'error' && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                Could not assess this transaction.
              </div>
            )}
            {assessStatus === 'ready' && selectedTransaction && assessment && (
              <TransactionDetail transaction={selectedTransaction} assessment={assessment} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
