import { apiRequest } from './client'

export type ColumnType =
  'string' | 'integer' | 'decimal' | 'currency' | 'date' | 'boolean' | 'enum'

export interface TemplateColumnCreate {
  name: string
  description?: string | null
  column_type: ColumnType
  enum_values?: string[] | null
  prompt_text?: string | null
  display_order: number
}

export interface TemplateCreate {
  domain_id: string
  name: string
  description?: string | null
  columns?: TemplateColumnCreate[]
}

export interface TemplateSummary {
  id: string
  domain_id: string
  name: string
  description: string | null
  version_number: number
  status: 'draft' | 'published'
  lock_version: number
  published_at: string | null
  updated_at: string
}

export interface TemplateColumn extends TemplateColumnCreate {
  id: string
  created_by_id: string
  updated_by_id: string
  created_at: string
  updated_at: string
}

export interface TemplateDetail {
  id: string
  domain_id: string
  created_by_id: string
  updated_by_id: string
  created_at: string
  updated_at: string
  current_version: {
    id: string
    version_number: number
    status: 'draft' | 'published'
    lock_version: number
    published_at: string | null
    published_by_id: string | null
    name: string
    description: string | null
    created_by_id: string
    updated_by_id: string
    created_at: string
    updated_at: string
    columns: TemplateColumn[]
  }
}

export function listTemplates(
  signal?: AbortSignal,
): Promise<TemplateSummary[]> {
  return apiRequest<TemplateSummary[]>('/templates', { signal })
}

export function createTemplate(data: TemplateCreate): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>('/templates', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface TemplateColumnDraft extends TemplateColumnCreate {
  id?: string
}

export interface TemplateDraftUpdate {
  domain_id: string
  name: string
  description?: string | null
  expected_lock_version: number
  columns: TemplateColumnDraft[]
}

export function getTemplate(
  templateId: string,
  signal?: AbortSignal,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}`, { signal })
}

export function updateTemplateDraft(
  templateId: string,
  data: TemplateDraftUpdate,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/draft`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function publishTemplate(
  templateId: string,
  expectedLockVersion: number,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/publish`, {
    method: 'POST',
    body: JSON.stringify({ expected_lock_version: expectedLockVersion }),
  })
}

export function addTemplateColumn(
  templateId: string,
  data: TemplateColumnCreate,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/columns`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
