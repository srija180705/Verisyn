import { useEffect, useState } from 'react'
import { PageHeading } from '../components/PageHeading'
import { apiGet } from '../lib/apiClient'
import type { RulesConfig } from '../lib/types'

type LoadStatus = 'loading' | 'ready' | 'error'

export function RulesPage() {
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [config, setConfig] = useState<RulesConfig | null>(null)

  async function load() {
    setStatus('loading')
    try {
      const result = await apiGet<RulesConfig>('/fraud/rules-config')
      setConfig(result)
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div>
      <PageHeading
        title="Rules"
        description="Read-only view of the deterministic rule engine and risk aggregation logic."
      />

      {status === 'error' && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Could not load rules configuration.{' '}
          <button onClick={load} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {status === 'loading' && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          Loading rules configuration...
        </div>
      )}

      {status === 'ready' && config && (
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
              Fraud Rules (max combined rule score: {config.max_rule_score})
            </div>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Rule</th>
                  <th className="px-4 py-2">Weight</th>
                  <th className="px-4 py-2">Condition</th>
                </tr>
              </thead>
              <tbody>
                {config.rules.map((rule) => (
                  <tr key={rule.name} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">{rule.name}</td>
                    <td className="px-4 py-2 text-slate-700">{rule.weight}</td>
                    <td className="px-4 py-2 text-slate-500">{rule.condition}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 text-sm font-medium text-slate-700">
                Signal Weights (final_risk_score)
              </div>
              <ul className="space-y-1 text-sm text-slate-700">
                {Object.entries(config.signal_weights).map(([signal, weight]) => (
                  <li key={signal} className="flex justify-between">
                    <span className="capitalize">{signal}</span>
                    <span>{(weight * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 text-sm font-medium text-slate-700">Risk Level Thresholds</div>
              <ul className="space-y-1 text-sm text-slate-700">
                {Object.entries(config.risk_level_thresholds).map(([name, value]) => (
                  <li key={name} className="flex justify-between">
                    <span className="font-mono text-xs">{name}</span>
                    <span>{value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 text-sm font-medium text-slate-700">
              Risk Level → Decision Mapping
            </div>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Risk Level</th>
                  <th className="px-4 py-2">Decision</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(config.decision_by_risk_level).map(([level, decision]) => (
                  <tr key={level} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-700">{level}</td>
                    <td className="px-4 py-2 text-slate-700">{decision}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
