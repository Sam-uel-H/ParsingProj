import { apiRequest } from './client'
import type { SelectionRectangle } from './taggedExamples'

export interface DryRunEvidence {
  quote: string
  page_number: number
  char_start: number
  char_end: number
  rectangles: SelectionRectangle[]
}

export interface PromptDryRun {
  prompt: string
  created_at: string
  expected_value: string
  status: 'valid' | 'invalid' | 'provider_error'
  actual_value?: string | null
  raw_output?: string | null
  validation_message?: string | null
  matches_expected?: boolean
  evidence?: DryRunEvidence | null
  evidence_verified: boolean
  provider_name?: string
  model_name?: string
  latency_ms?: number
}

export interface PromptDraft {
  id: string
  template_column_id: string
  document_id: string
  document_extraction_id: string
  expected_value: string
  suggested_prompt: string
  edited_prompt: string
  dry_runs: PromptDryRun[]
  accepted: boolean
  provider_name: string
  model_name: string
  created_by_id: string
  created_at: string
  updated_at: string
}

const path = (templateId: string) => `/templates/${templateId}/prompt-drafts`

export function listPromptDrafts(
  templateId: string,
  columnId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<PromptDraft[]> {
  const params = new URLSearchParams({
    column_id: columnId,
    document_id: documentId,
  })
  return apiRequest(`${path(templateId)}?${params}`, { signal })
}

export function generatePrompt(
  templateId: string,
  columnId: string,
  documentId: string,
): Promise<PromptDraft> {
  return apiRequest(path(templateId), {
    method: 'POST',
    body: JSON.stringify({
      template_column_id: columnId,
      document_id: documentId,
    }),
  })
}

export function editPrompt(
  templateId: string,
  draftId: string,
  editedPrompt: string,
): Promise<PromptDraft> {
  return apiRequest(`${path(templateId)}/${draftId}`, {
    method: 'PUT',
    body: JSON.stringify({ edited_prompt: editedPrompt }),
  })
}

export function dryRunPrompt(
  templateId: string,
  draftId: string,
): Promise<PromptDraft> {
  return apiRequest(`${path(templateId)}/${draftId}/dry-runs`, {
    method: 'POST',
  })
}

export function acceptPrompt(
  templateId: string,
  draftId: string,
  expectedLockVersion: number,
): Promise<PromptDraft> {
  return apiRequest(`${path(templateId)}/${draftId}/accept`, {
    method: 'POST',
    body: JSON.stringify({ expected_lock_version: expectedLockVersion }),
  })
}
