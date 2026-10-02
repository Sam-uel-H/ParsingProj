export interface TaskProgress {
  id: string
  state: string
  attempts: number
  max_attempts: number
  completed_units: number
  total_units: number
  error_code: string | null
  error_message: string | null
  retryable: boolean
  available_at: string
}

export function isJobActive(status?: string): boolean {
  return ['queued', 'extracting', 'parsing', 'running', 'processing'].includes(
    status ?? '',
  )
}
