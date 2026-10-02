import { expect, type APIRequestContext } from '@playwright/test'
import type { DocumentExtractionRecord } from '../src/api/documents'

export async function waitForExtraction(
  request: APIRequestContext,
  documentId: string,
): Promise<DocumentExtractionRecord> {
  const url = `http://127.0.0.1:8000/documents/${documentId}/extraction`
  await expect
    .poll(async () => (await (await request.get(url)).json()).status, {
      timeout: 30_000,
    })
    .toBe('succeeded')
  return (await request.get(url)).json()
}
