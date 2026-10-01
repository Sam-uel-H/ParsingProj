import { apiRequest } from './client'

export interface SelectionRectangle {
  x: number
  y: number
  width: number
  height: number
}

export interface TaggedExampleWrite {
  template_column_id: string
  document_id: string
  document_extraction_id: string
  page_number: number
  selected_text: string
  expected_value: string
  rectangles: SelectionRectangle[]
}

export interface TaggedExample {
  id: string
  template_column_id: string
  document_id: string
  document_extraction_id: string
  tagged_value: string
  expected_value: string
  page_number: number
  char_start: number
  char_end: number
  rectangles: SelectionRectangle[]
  text_block_ids: string[]
  created_by_id: string
  created_at: string
}

const path = (templateId: string) => `/templates/${templateId}/tagged-examples`

export function listTaggedExamples(
  templateId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<TaggedExample[]> {
  return apiRequest<TaggedExample[]>(
    `${path(templateId)}?document_id=${encodeURIComponent(documentId)}`,
    { signal },
  )
}

export function createTaggedExample(
  templateId: string,
  data: TaggedExampleWrite,
): Promise<TaggedExample> {
  return apiRequest<TaggedExample>(path(templateId), {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function replaceTaggedExample(
  templateId: string,
  tagId: string,
  data: TaggedExampleWrite,
): Promise<TaggedExample> {
  return apiRequest<TaggedExample>(`${path(templateId)}/${tagId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteTaggedExample(
  templateId: string,
  tagId: string,
): Promise<void> {
  return apiRequest<void>(`${path(templateId)}/${tagId}`, {
    method: 'DELETE',
  })
}
