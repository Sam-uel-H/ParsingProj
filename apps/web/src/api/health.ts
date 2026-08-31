export interface HealthResponse {
  status: 'ok' | 'unavailable'
  service: string
  version: string
  checks: Record<string, string>
}

function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  return `${base.replace(/\/$/, '')}${path}`
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(apiUrl('/health'), { signal })
  if (!response.ok) {
    throw new Error(`Health request failed (${response.status})`)
  }
  return (await response.json()) as HealthResponse
}
