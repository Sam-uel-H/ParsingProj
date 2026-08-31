import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HealthStatus } from './HealthStatus'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HealthStatus', () => {
  it('shows successful backend connectivity', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'ok',
            service: 'Document Parsing System API',
            version: '0.1.0',
            checks: {},
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <HealthStatus />
      </QueryClientProvider>,
    )

    expect(
      await screen.findByText(/Connected to Document Parsing System API/),
    ).toBeVisible()
  })
})
