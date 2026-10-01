export interface ApiErrorBody {
  request_id?: string
  error?: {
    code?: string
    message?: string
    details?: unknown
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string = 'api_error',
    public readonly details?: unknown,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  return `${base.replace(/\/$/, '')}${path}`
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(apiUrl(path), { ...init, headers })
  if (!response.ok) {
    let body: ApiErrorBody = {}
    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // A proxy or network edge may return a non-JSON error page.
    }
    throw new ApiError(
      body.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body.error?.code,
      body.error?.details,
      body.request_id,
    )
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T
  }
  return (await response.json()) as T
}
