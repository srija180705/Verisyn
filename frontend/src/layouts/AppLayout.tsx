import { Outlet } from 'react-router-dom'
import { NavLinkItem } from '../components/NavLinkItem'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/investigations', label: 'Investigations' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/rules', label: 'Rules' },
]

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="text-lg font-semibold text-slate-900">
            Fraud Intelligence Platform
          </span>
          <nav className="flex gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLinkItem key={item.to} to={item.to} label={item.label} />
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
