import { PageHeading } from '../components/PageHeading'

export function DashboardPage() {
  return (
    <div>
      <PageHeading
        title="Dashboard"
        description="Fraud operations overview. Real-time metrics will be implemented in a later phase."
      />
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
        Dashboard functionality is not yet implemented.
      </div>
    </div>
  )
}
