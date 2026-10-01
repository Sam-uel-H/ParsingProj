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
  status: 'draft' | 'published' | 'archived'
  lock_version: number
  published_at: string | null
  created_by_id: string
  created_by_name: string
  archived_at: string | null
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
  archived_at: string | null
  archived_by_id: string | null
  current_version: TemplateVersion
}

export interface TemplateVersion {
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

export interface TemplateFilters {
  search?: string
  domainId?: string
  author?: string
  status?: '' | 'draft' | 'published' | 'archived'
}

export function listTemplates(
  filters: TemplateFilters = {},
  signal?: AbortSignal,
): Promise<TemplateSummary[]> {
  const params = new URLSearchParams()
  if (filters.search) params.set('search', filters.search)
  if (filters.domainId) params.set('domain_id', filters.domainId)
  if (filters.author) params.set('author', filters.author)
  if (filters.status) params.set('status', filters.status)
  const query = params.size > 0 ? `?${params.toString()}` : ''
  return apiRequest<TemplateSummary[]>(`/templates${query}`, { signal })
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

export function listTemplateVersions(
  templateId: string,
  signal?: AbortSignal,
): Promise<TemplateVersion[]> {
  return apiRequest<TemplateVersion[]>(`/templates/${templateId}/versions`, {
    signal,
  })
}

export function createTemplateVersion(
  templateId: string,
  sourceVersionId?: string,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/versions`, {
    method: 'POST',
    body: JSON.stringify({ source_version_id: sourceVersionId ?? null }),
  })
}

export function cloneTemplate(
  templateId: string,
  name: string,
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/clone`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function archiveTemplate(templateId: string): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/archive`, {
    method: 'POST',
  })
}

export function deleteTemplate(templateId: string): Promise<void> {
  return apiRequest<void>(`/templates/${templateId}`, { method: 'DELETE' })
}

export function reorderTemplateColumns(
  templateId: string,
  expectedLockVersion: number,
  columnIds: string[],
): Promise<TemplateDetail> {
  return apiRequest<TemplateDetail>(`/templates/${templateId}/columns/order`, {
    method: 'PUT',
    body: JSON.stringify({
      expected_lock_version: expectedLockVersion,
      column_ids: columnIds,
    }),
  })
}
