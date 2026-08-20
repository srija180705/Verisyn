// Minimal fetch-based API client - apiGet/apiPost cover everything the
// dashboard needs (GET /transactions, POST /fraud/assess).

// 127.0.0.1 (not "localhost") avoids ambiguity when both IPv4 and IPv6
// loopback listeners exist on the same port - the browser can otherwise
// resolve "localhost" to a different service on ::1 than the one on 127.0.0.1.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}
