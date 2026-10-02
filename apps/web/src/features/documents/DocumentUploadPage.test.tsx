import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DocumentUploadPage } from './DocumentUploadPage'

vi.mock('../../api/domains', () => ({
  listDomains: vi.fn(),
}))

vi.mock('../../api/documents', () => ({
  uploadDocuments: vi.fn(),
  extractDocument: vi.fn(),
}))

import { extractDocument, uploadDocuments } from '../../api/documents'
import { listDomains } from '../../api/domains'

const mockedListDomains = vi.mocked(listDomains)
const mockedUploadDocuments = vi.mocked(uploadDocuments)
const mockedExtractDocument = vi.mocked(extractDocument)

afterEach(cleanup)

describe('DocumentUploadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedListDomains.mockResolvedValue([])
    mockedExtractDocument.mockResolvedValue({
      id: 'extraction-1',
      document_id: 'document-1',
      status: 'succeeded',
      provider_name: 'fake',
      provider_version: '1',
      full_text: 'hello',
      error_code: null,
      error_message: null,
      started_at: '2026-08-24T00:00:00Z',
      completed_at: '2026-08-24T00:00:01Z',
      pages: [],
    })
    mockedUploadDocuments.mockImplementation(
      async ([file], _domainId, onProgress) => {
        onProgress?.(100)
        const success = file.name.endsWith('.txt')
        return {
          results: [
            {
              file_name: file.name,
              success,
              document: success
                ? {
                    id: 'document-1',
                    domain_id: null,
                    original_file_name: file.name,
                    file_type: 'text',
                    content_type: 'text/plain',
                    file_size: file.size,
                    checksum_sha256: 'a'.repeat(64),
                    upload_status: 'stored',
                    processing_status: 'pending',
                    uploaded_by_id: 'user-1',
                    uploaded_at: '2026-08-24T00:00:00Z',
                    active_extraction_id: null,
                  }
                : null,
              error: success
                ? null
                : { code: 'invalid_upload', message: 'Unsupported file.' },
            },
          ],
        }
      },
    )
  })

  it('uploads selected files independently and displays each result', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DocumentUploadPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const good = new File(['hello'], 'notice.txt', { type: 'text/plain' })
    const bad = new File(['bad'], 'program.exe', {
      type: 'application/octet-stream',
    })

    fireEvent.change(screen.getByLabelText('Document files'), {
      target: { files: [good, bad] },
    })
    fireEvent.click(
      screen.getByRole('button', { name: 'Upload selected files' }),
    )

    expect(
      await screen.findByText('Upload completed. Extraction queued.'),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: 'Open document' })).toHaveAttribute(
      'href',
      '/documents/document-1',
    )
    expect(await screen.findByText('Unsupported file.')).toBeVisible()
    await waitFor(() => expect(mockedUploadDocuments).toHaveBeenCalledTimes(2))
    expect(mockedUploadDocuments).toHaveBeenCalledWith(
      [good],
      null,
      expect.any(Function),
    )
    expect(mockedUploadDocuments).toHaveBeenCalledWith(
      [bad],
      null,
      expect.any(Function),
    )
  })
})
