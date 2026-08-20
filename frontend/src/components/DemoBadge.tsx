// DEMO- prefixed transactions are seeded by ml/data/seed_demo.py to
// exercise specific fraud scenarios - never part of the original dataset.
// This badge just makes that visible at a glance; the prefix check is the
// only "logic" here, nothing structural depends on it.
export function isDemoTransaction(externalTransactionId: string): boolean {
  return externalTransactionId.startsWith('DEMO-')
}

export function DemoBadge() {
  return (
    <span className="inline-block rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
      Demo
    </span>
  )
}
