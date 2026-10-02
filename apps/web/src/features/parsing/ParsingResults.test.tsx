import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ParsingJob } from '../../api/parsing'
import { ParsingResults } from './ParsingResults'

vi.mock('../../api/parsing', async () => {
  const actual =
    await vi.importActual<typeof import('../../api/parsing')>(
      '../../api/parsing',
    )
  return {
    ...actual,
    correctParsingResult: vi.fn(),
    parsingExportUrl: vi.fn(
      (jobId: string, format: 'csv' | 'json') =>
        `/api/parsing-jobs/${jobId}/export.${format}`,
    ),
  }
})

import { correctParsingResult } from '../../api/parsing'

const mockedCorrectParsingResult = vi.mocked(correctParsingResult)

afterEach(cleanup)

function job(): ParsingJob {
  return {
    id: 'job-1',
    document_id: 'document-1',
    template_id: 'template-1',
    template_version_id: 'version-1',
    status: 'completed_with_warnings',
    domain_override: false,
    started_by_id: 'user-1',
    started_at: '2026-09-11T12:00:00Z',
    completed_at: '2026-09-11T12:00:01Z',
    results: [
      {
        id: 'result-1',
        template_column_id: 'column-1',
        column_name: 'Amount',
        column_type: 'currency',
        enum_values: null,
        raw_output: '{"value": "oops"}',
        canonical_value: null,
        reviewed_value: null,
        current_value: null,
        validation_status: 'needs_review',
        validation_message: 'Expected a currency value.',
        confidence: 0.2,
        retry_count: 2,
        human_verified: false,
        reviewed_by_id: null,
        reviewed_at: null,
      },
    ],
  }
}

function renderResults(data = job()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ParsingResults job={data} />
    </QueryClientProvider>,
  )
}

describe('ParsingResults', () => {
  it('shows progress without allowing review or export before completion', () => {
    renderResults({
      ...job(),
      status: 'queued',
      progress: {
        id: 'task-1',
        state: 'queued',
        attempts: 1,
        max_attempts: 4,
        completed_units: 2,
        total_units: 5,
        error_code: 'provider_rate_limited',
        error_message: 'Provider rate limit reached.',
        retryable: true,
        available_at: '2026-10-02T12:00:00Z',
      },
    })
    expect(
      screen.getByRole('progressbar', { name: 'Job progress' }),
    ).toHaveAttribute('aria-valuenow', '40')
    expect(screen.getByText(/Retrying after/)).toBeVisible()
    expect(
      screen.queryByRole('link', { name: 'Export CSV' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Reviewed value')).not.toBeInTheDocument()
  })

  it('saves a reviewed correction and exposes export actions', async () => {
    mockedCorrectParsingResult.mockResolvedValue({
      ...job().results[0],
      reviewed_value: '1234.50',
      current_value: '1234.50',
      validation_status: 'valid',
      validation_message: null,
      human_verified: true,
      reviewed_by_id: 'user-1',
      reviewed_at: '2026-09-11T12:05:00Z',
    })
    renderResults()

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/parsing-jobs/job-1/export.csv',
    )
    fireEvent.change(screen.getByLabelText('Reviewed value'), {
      target: { value: '1234.50' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockedCorrectParsingResult).toHaveBeenCalledWith(
        'job-1',
        'result-1',
        '1234.50',
      )
    })
    expect(await screen.findByText('Human verified')).toBeVisible()
  })
})
