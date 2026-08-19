interface PageHeadingProps {
  title: string
  description: string
}

export function PageHeading({ title, description }: PageHeadingProps) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  )
}
