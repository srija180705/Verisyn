import type { KeyboardEvent } from 'react'

// Makes a clickable table row keyboard-activatable with Enter/Space,
// matching native button behavior. Used by any page with onClick rows
// (Dashboard, Transactions, Investigations).
export function onRowKeyDown(onActivate: () => void) {
  return (event: KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onActivate()
    }
  }
}
