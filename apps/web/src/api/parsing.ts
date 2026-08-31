import { apiRequest } from './client'

export interface ParsingResult {
  id: string
  template_column_id: string
  column_name: string
  raw_output: string | null
  canonical_value: string | null
  validation_status: 'valid' | 'needs_review'
  validation_message: string | null
  confidence: number | null
  retry_count: number
}

export interface ParsingJob {
  id: string
  document_id: string
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
