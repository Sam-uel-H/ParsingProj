import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DocumentDetailPage } from './DocumentDetailPage'

vi.mock('../../api/documents', () => ({
  getDocument: vi.fn(),
  getDocumentExtraction: vi.fn(),
  extractDocument: vi.fn(),
  reprocessDocument: vi.fn(),
  listExtractions: vi.fn().mockResolvedValue([]),
  documentContentUrl: vi.fn(() => '/content'),
  documentPagePreviewUrl: vi.fn((_id, page) => `/preview/${page}`),
}))

import { getDocument, getDocumentExtraction } from '../../api/documents'

afterEach(cleanup)

describe('DocumentDetailPage', () => {
  it('navigates pages, zooms, and switches to extracted text', async () => {
    vi.mocked(getDocument).mockResolvedValue({
      id: 'document-1',
      domain_id: null,
      original_file_name: 'notice.txt',
      file_type: 'text',
      content_type: 'text/plain',
      file_size: 10,
      checksum_sha256: 'a'.repeat(64),
      upload_status: 'stored',
      processing_status: 'succeeded',
      uploaded_by_id: 'user-1',
      uploaded_at: '2026-08-24T00:00:00Z',
      active_extraction_id: 'extraction-1',
    })
    vi.mocked(getDocumentExtraction).mockResolvedValue({
      id: 'extraction-1',
      document_id: 'document-1',
      status: 'succeeded',
      provider_name: 'fake',
      provider_version: '1',
      full_text: 'page one\fpage two',
      error_code: null,
      error_message: null,
      started_at: '2026-08-24T00:00:00Z',
      completed_at: '2026-08-24T00:00:01Z',
      pages: [1, 2].map((page) => ({
        id: `page-${page}`,
        page_number: page,
        text: `page ${page === 1 ? 'one' : 'two'}`,
        width: 612,
        height: 792,
        preview_content_type: 'image/svg+xml',
        blocks: [],
      })),
    })
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/documents/document-1']}>
          <Routes>
            <Route
              path="/documents/:documentId"
              element={<DocumentDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Page 1 of 2')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('Page 2 of 2')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(screen.getByText('125%')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Extracted text' }))
    expect(screen.getByText('page two')).toBeVisible()
  })
})
