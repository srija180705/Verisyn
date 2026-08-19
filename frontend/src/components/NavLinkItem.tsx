import { NavLink } from 'react-router-dom'

interface NavLinkItemProps {
  to: string
  label: string
}

export function NavLinkItem({ to, label }: NavLinkItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? 'bg-slate-900 text-white'
            : 'text-slate-600 hover:bg-slate-200 hover:text-slate-900'
        }`
      }
    >
      {label}
    </NavLink>
  )
}
