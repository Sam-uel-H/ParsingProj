import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DomainsPage } from './DomainsPage'

vi.mock('../../api/domains', () => ({
  listDomains: vi.fn(),
  createDomain: vi.fn(),
}))

import { listDomains } from '../../api/domains'

const mockedListDomains = vi.mocked(listDomains)

describe('DomainsPage', () => {
  beforeEach(() => {
    mockedListDomains.mockResolvedValue([
      {
        id: 'domain-1',
        name: 'Agent Bank Notices',
        description: 'Interest and payment notices',
        created_by_id: 'user-1',
        updated_by_id: 'user-1',
        created_at: '2026-08-23T12:00:00Z',
        updated_at: '2026-08-23T12:00:00Z',
      },
    ])
  })

  it('lists domains returned by the API client', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <DomainsPage />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Agent Bank Notices')).toBeVisible()
    expect(screen.getByText('Interest and payment notices')).toBeVisible()
  })
})
