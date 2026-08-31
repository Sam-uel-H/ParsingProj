import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TemplateDetail } from '../../api/templates'
import { TemplateEditorPage } from './TemplateEditorPage'

vi.mock('../../api/domains', () => ({
  listDomains: vi.fn(),
}))

vi.mock('../../api/templates', () => ({
  getTemplate: vi.fn(),
  createTemplate: vi.fn(),
  updateTemplateDraft: vi.fn(),
  publishTemplate: vi.fn(),
}))

import { listDomains } from '../../api/domains'
import { getTemplate, updateTemplateDraft } from '../../api/templates'

const mockedListDomains = vi.mocked(listDomains)
const mockedGetTemplate = vi.mocked(getTemplate)
const mockedUpdateTemplateDraft = vi.mocked(updateTemplateDraft)

afterEach(cleanup)

function detail(status: 'draft' | 'published' = 'draft'): TemplateDetail {
  return {
    id: 'template-1',
    domain_id: 'domain-1',
    created_by_id: 'user-1',
    updated_by_id: 'user-1',
    created_at: '2026-08-23T12:00:00Z',
    updated_at: '2026-08-23T12:00:00Z',
    current_version: {
      id: 'version-1',
      version_number: 1,
      status,
      lock_version: status === 'draft' ? 1 : 2,
      published_at: status === 'published' ? '2026-08-23T13:00:00Z' : null,
      published_by_id: status === 'published' ? 'user-1' : null,
      name: 'Payment Notice',
      description: 'A payment notice template',
      created_by_id: 'user-1',
      updated_by_id: 'user-1',
      created_at: '2026-08-23T12:00:00Z',
      updated_at: '2026-08-23T12:00:00Z',
      columns: [
        {
          id: 'column-1',
          name: 'Amount',
          description: null,
          column_type: 'currency',
          enum_values: null,
          prompt_text: 'Extract the amount due.',
          display_order: 0,
          created_by_id: 'user-1',
          updated_by_id: 'user-1',
          created_at: '2026-08-23T12:00:00Z',
          updated_at: '2026-08-23T12:00:00Z',
        },
      ],
    },
  }
}

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/templates/template-1']}>
        <Routes>
          <Route
            path="/templates/:templateId"
            element={<TemplateEditorPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TemplateEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedListDomains.mockResolvedValue([
      {
        id: 'domain-1',
        name: 'Loan Notices',
        description: null,
        created_by_id: 'user-1',
        updated_by_id: 'user-1',
        created_at: '2026-08-23T12:00:00Z',
        updated_at: '2026-08-23T12:00:00Z',
      },
    ])
  })

  it('saves a changed draft with its optimistic lock version', async () => {
    const initial = detail()
    const saved = detail()
    saved.current_version.name = 'Updated Payment Notice'
    saved.current_version.lock_version = 2
    mockedGetTemplate.mockResolvedValue(initial)
    mockedUpdateTemplateDraft.mockResolvedValue(saved)
    renderEditor()

    const name = await screen.findByLabelText('Template name')
    fireEvent.change(name, { target: { value: 'Updated Payment Notice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

    await waitFor(() => {
      expect(mockedUpdateTemplateDraft).toHaveBeenCalledWith(
        'template-1',
        expect.objectContaining({
          name: 'Updated Payment Notice',
          expected_lock_version: 1,
        }),
      )
    })
  })

  it('renders a published version as read-only', async () => {
    mockedGetTemplate.mockResolvedValue(detail('published'))
    renderEditor()

    expect(await screen.findByLabelText('Template name')).toBeDisabled()
    expect(screen.getByText(/published and is read-only/i)).toBeVisible()
    expect(
      screen.queryByRole('button', { name: 'Save draft' }),
    ).not.toBeInTheDocument()
  })
})
