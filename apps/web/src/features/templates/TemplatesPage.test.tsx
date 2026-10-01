import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  TemplateDetail,
  TemplateSummary,
  TemplateVersion,
} from '../../api/templates'
import { TemplateHistoryPage } from './TemplateHistoryPage'
import { TemplatesPage } from './TemplatesPage'

vi.mock('../../api/domains', () => ({ listDomains: vi.fn() }))
vi.mock('../../api/templates', () => ({
  listTemplates: vi.fn(),
  getTemplate: vi.fn(),
  listTemplateVersions: vi.fn(),
  createTemplateVersion: vi.fn(),
  archiveTemplate: vi.fn(),
  cloneTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
}))

import { listDomains } from '../../api/domains'
import {
  createTemplateVersion,
  getTemplate,
  listTemplates,
  listTemplateVersions,
} from '../../api/templates'

const mockedListDomains = vi.mocked(listDomains)
const mockedListTemplates = vi.mocked(listTemplates)
const mockedGetTemplate = vi.mocked(getTemplate)
const mockedListVersions = vi.mocked(listTemplateVersions)
const mockedCreateVersion = vi.mocked(createTemplateVersion)

const summary: TemplateSummary = {
  id: 'template-1',
  domain_id: 'domain-1',
  name: 'Payment Notice',
  description: 'Section 6 payment notice',
  version_number: 1,
  status: 'published',
  lock_version: 2,
  published_at: '2026-09-26T12:00:00Z',
  created_by_id: 'user-1',
  created_by_name: 'Development User',
  archived_at: null,
  updated_at: '2026-09-26T12:00:00Z',
}

const version: TemplateVersion = {
  id: 'version-1',
  version_number: 1,
  status: 'published',
  lock_version: 2,
  published_at: '2026-09-26T12:00:00Z',
  published_by_id: 'user-1',
  name: 'Payment Notice',
  description: 'Section 6 payment notice',
  created_by_id: 'user-1',
  updated_by_id: 'user-1',
  created_at: '2026-09-26T11:00:00Z',
  updated_at: '2026-09-26T12:00:00Z',
  columns: [
    {
      id: 'column-1',
      name: 'Amount',
      description: null,
      column_type: 'currency',
      enum_values: null,
      prompt_text: 'Extract the amount.',
      display_order: 0,
      created_by_id: 'user-1',
      updated_by_id: 'user-1',
      created_at: '2026-09-26T11:00:00Z',
      updated_at: '2026-09-26T11:00:00Z',
    },
  ],
}

const detail: TemplateDetail = {
  id: summary.id,
  domain_id: summary.domain_id,
  created_by_id: 'user-1',
  updated_by_id: 'user-1',
  created_at: '2026-09-26T11:00:00Z',
  updated_at: '2026-09-26T12:00:00Z',
  archived_at: null,
  archived_by_id: null,
  current_version: version,
}

function renderAt(path: string, element: ReactNode, routePattern = '*') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePattern} element={element} />
          <Route
            path="/templates/:templateId"
            element={<div>Template editor</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(cleanup)

describe('Phase 8 template lifecycle UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedListDomains.mockResolvedValue([
      {
        id: 'domain-1',
        name: 'Agent Bank Notices',
        description: null,
        created_by_id: 'user-1',
        updated_by_id: 'user-1',
        created_at: '2026-09-26T11:00:00Z',
        updated_at: '2026-09-26T11:00:00Z',
      },
    ])
    mockedListTemplates.mockResolvedValue([summary])
  })

  it('browses templates and sends search and status filters', async () => {
    renderAt('/templates', <TemplatesPage />)

    expect(await screen.findByText('Payment Notice')).toBeVisible()
    expect(screen.getByText('published v1')).toBeVisible()

    fireEvent.change(screen.getByLabelText('Search name or description'), {
      target: { value: 'interest' },
    })
    fireEvent.mouseDown(screen.getByLabelText('Status'))
    fireEvent.click(await screen.findByRole('option', { name: 'Published' }))

    await waitFor(() => {
      expect(mockedListTemplates).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'interest', status: 'published' }),
        expect.any(AbortSignal),
      )
    })
  })

  it('shows immutable version details and creates the next draft', async () => {
    mockedGetTemplate.mockResolvedValue(detail)
    mockedListVersions.mockResolvedValue([version])
    mockedCreateVersion.mockResolvedValue({
      ...detail,
      current_version: {
        ...version,
        id: 'version-2',
        version_number: 2,
        status: 'draft',
      },
    })
    renderAt(
      '/templates/template-1/history',
      <TemplateHistoryPage />,
      '/templates/:templateId/history',
    )

    expect(await screen.findByText('Version 1: Payment Notice')).toBeVisible()
    expect(screen.getByText('Extract the amount.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Create new version' }))

    await waitFor(() => {
      expect(mockedCreateVersion).toHaveBeenCalledWith('template-1')
    })
  })
})
