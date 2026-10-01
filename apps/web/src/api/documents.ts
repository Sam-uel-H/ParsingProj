import { ApiError, apiRequest, type ApiErrorBody } from './client'

export type DocumentFileType = 'pdf' | 'docx' | 'tiff' | 'png' | 'jpeg' | 'text'

export interface DocumentRecord {
  id: string
  domain_id: string | null
  original_file_name: string
  file_type: DocumentFileType
  content_type: string
  file_size: number
  checksum_sha256: string
  upload_status: 'stored'
  processing_status: 'pending' | 'processing' | 'succeeded' | 'failed'
  uploaded_by_id: string
  uploaded_at: string
  active_extraction_id: string | null
}

export interface TextBlockRecord {
  id: string
  text: string
  reading_order: number
  char_start: number
  char_end: number
  polygon: { x: number; y: number }[]
  confidence: number | null
}

export interface DocumentPageRecord {
  id: string
  page_number: number
  text: string
  width: number
  height: number
  preview_content_type: string
  blocks: TextBlockRecord[]
}

export interface DocumentExtractionRecord {
  id: string
  document_id: string
  status: 'processing' | 'succeeded' | 'failed'
  provider_name: string | null
  provider_version: string | null
  full_text: string | null
  error_code: string | null
  error_message: string | null
  started_at: string
  completed_at: string | null
  pages: DocumentPageRecord[]
}

export interface DocumentUploadResult {
  file_name: string
  success: boolean
  document: DocumentRecord | null
  error: { code: string; message: string } | null
}

export interface DocumentUploadBatch {
  results: DocumentUploadResult[]
}

function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  return `${base.replace(/\/$/, '')}${path}`
}

export function listDocuments(signal?: AbortSignal): Promise<DocumentRecord[]> {
  return apiRequest<DocumentRecord[]>('/documents', { signal })
}

export function getDocument(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  return apiRequest<DocumentRecord>(`/documents/${documentId}`, { signal })
}

export function documentContentUrl(documentId: string): string {
  return apiUrl(`/documents/${documentId}/content`)
}

export function extractDocument(
  documentId: string,
): Promise<DocumentExtractionRecord> {
  return apiRequest<DocumentExtractionRecord>(
    `/documents/${documentId}/extract`,
    {
      method: 'POST',
    },
  )
}

export function getDocumentExtraction(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentExtractionRecord> {
  return apiRequest<DocumentExtractionRecord>(
    `/documents/${documentId}/extraction`,
    { signal },
  )
}

export function documentPagePreviewUrl(
  documentId: string,
  pageNumber: number,
): string {
  return apiUrl(`/documents/${documentId}/pages/${pageNumber}/preview`)
}

export function uploadDocuments(
  files: File[],
  domainId: string | null,
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadBatch> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', apiUrl('/documents/upload'))
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100))
      }
    }
    request.onerror = () =>
      reject(new ApiError('Upload failed due to a network error.', 0))
    request.onload = () => {
      let body: DocumentUploadBatch | ApiErrorBody
      try {
        body = JSON.parse(request.responseText) as
          DocumentUploadBatch | ApiErrorBody
      } catch {
        reject(
          new ApiError(`Upload failed (${request.status})`, request.status),
        )
        return
      }
      if (request.status < 200 || request.status >= 300) {
        const errorBody = body as ApiErrorBody
        reject(
          new ApiError(
            errorBody.error?.message ?? `Upload failed (${request.status})`,
            request.status,
            errorBody.error?.code,
            errorBody.error?.details,
            errorBody.request_id,
          ),
        )
        return
      }
      resolve(body as DocumentUploadBatch)
    }

    const form = new FormData()
    files.forEach((file) => form.append('files', file, file.name))
    if (domainId) form.append('domain_id', domainId)
    request.send(form)
  })
}
