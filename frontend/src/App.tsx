import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { InvestigationsPage } from './pages/InvestigationsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { RulesPage } from './pages/RulesPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="investigations" element={<InvestigationsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="rules" element={<RulesPage />} />
      </Route>
    </Routes>
  )
}
