import { apiRequest, apiUrl } from './client'

export type ParsingColumnType =
  'string' | 'integer' | 'decimal' | 'currency' | 'date' | 'boolean' | 'enum'

export interface ParsingResult {
  id: string
  template_column_id: string
  column_name: string
  column_type: ParsingColumnType
  enum_values: string[] | null
  raw_output: string | null
  canonical_value: string | null
  reviewed_value: string | null
  current_value: string | null
  validation_status: 'valid' | 'needs_review'
  validation_message: string | null
  confidence: number | null
  retry_count: number
  human_verified: boolean
  reviewed_by_id: string | null
  reviewed_at: string | null
}

export interface ParsingJob {
  id: string
  document_id: string
  template_id: string
  template_version_id: string
  status: 'running' | 'completed' | 'completed_with_warnings' | 'failed'
  domain_override: boolean
  started_by_id: string
  started_at: string
  completed_at: string | null
  results: ParsingResult[]
}

export function runParsingJob(data: {
  document_id: string
  template_id: string
  confirm_domain_override: boolean
}): Promise<ParsingJob> {
  return apiRequest<ParsingJob>('/parsing-jobs', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getParsingJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<ParsingJob> {
  return apiRequest<ParsingJob>(`/parsing-jobs/${jobId}`, { signal })
}

export function correctParsingResult(
  jobId: string,
  resultId: string,
  value: string | number | boolean | null,
): Promise<ParsingResult> {
  return apiRequest<ParsingResult>(
    `/parsing-jobs/${jobId}/results/${resultId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ value }),
    },
  )
}

export function parsingExportUrl(
  jobId: string,
  format: 'csv' | 'json',
): string {
  return apiUrl(`/parsing-jobs/${jobId}/export.${format}`)
}
